"""Flows with a scripted LLM and the fake mailbox (memory persister)."""

import re

import pytest

from app.agent import flows
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.loop import PhaseFailed
from app.mail.fake import FakeMailbox
from tests.helpers import GOOD_APP, SMALL_MAILBOX, ScriptedLLM, dt, tool_results

GUIDE = "# Purpose\nOrders.\n\n# Record types\n## order\n\n# What to ignore\n\n# Learned\n"


def make(now="2026-10-16T00:00:00Z", state=None, persister=None):
    box = FakeMailbox.from_file(SMALL_MAILBOX, now=dt(now))
    p = persister or MemoryPersister()
    st = state or WorkspaceState(prompt="track orders")
    p.state = st
    ctx = RunContext(state=st, mailbox=box, persister=p, run_id="r", now=dt(now))
    return ctx, box, p


def cfg(llm, batch=8):
    return flows.FlowConfig(llm=llm, build_model="b", sync_model="s", batch_threads=batch)


def save_all_new(messages):
    """Process-batch turn: save one order per thread from the batch input."""
    user = messages[1]["content"]
    records = []
    for tid, block in re.findall(r'<thread id="(\w+)">(.*?)</thread>', user, re.S):
        mids = re.findall(r'<message id="(\w+)"[^>]*new="true"', block)
        if mids and "Order" in block and "digest" not in block:
            records.append(
                {"id": f"o-{tid}", "fields": {"seen": len(mids)}, "source_message_ids": mids}
            )
    if not records:
        return [("finish", {"summary": "No changes"})]
    return [
        ("save_records", {"record_type": "order", "records": records}),
        ("finish", {"summary": f"{len(records)} orders"}),
    ]


DESIGN_TURNS = [
    [("search_mail", {"query": "order"})],
    [("write_guide", {"text": GUIDE}), ("set_queries", {"queries": ["order"]})],
    [("finish", {"summary": "Tracks orders."})],
]


async def test_build_happy_path():
    ctx, _, p = make()
    llm = ScriptedLLM(
        DESIGN_TURNS
        + [save_all_new, [("write_app", {"html": GOOD_APP})], [("finish", {"summary": "table"})]]
    )
    summary = await flows.build(ctx, cfg(llm))
    assert "Built from 6 threads" in summary
    assert len(ctx.state.data["order"]) >= 3
    assert ctx.state.app_html == GOOD_APP and ctx.state.last_synced_at == ctx.now
    assert len(p.processed) == 7  # every message of the 6 visible threads
    assert p.snapshots, "build takes a snapshot first"
    labels = [e["label"] for e in p.events]
    assert "Reading your emails (batch 1 of 1)" in labels


async def test_build_cannot_build():
    ctx, _, _ = make()
    llm = ScriptedLLM(
        [[("finish", {"summary": "CANNOT_BUILD: your step counts are not in email."})]]
    )
    with pytest.raises(flows.CannotBuild, match="step counts"):
        await flows.build(ctx, cfg(llm))


async def test_design_finish_without_guide_is_rejected_then_fails():
    ctx, _, _ = make()
    llm = ScriptedLLM([[("finish", {"summary": "done"})]] * 3)
    with pytest.raises(PhaseFailed, match="3 times"):
        await flows.build(ctx, cfg(llm))
    assert "write_guide" in tool_results(llm.calls[1])[0]["error"]


async def test_failed_batch_is_skipped_and_build_continues():
    ctx, _, p = make()
    bad = [("read_thread", {"thread_id": "nope"})]
    llm = ScriptedLLM(
        DESIGN_TURNS
        + [bad] * 6  # batch 1: two attempts × three errors
        + [save_all_new]  # batch 2
        + [[("write_app", {"html": GOOD_APP})], [("finish", {"summary": "ok"})]]
    )
    await flows.build(ctx, cfg(llm, batch=3))
    assert any("Skipped batch 1" in e["label"] for e in p.events)
    assert ctx.state.data["order"]


async def test_app_phase_failure_falls_back_to_default_app():
    ctx, _, p = make()
    llm = ScriptedLLM(DESIGN_TURNS + [save_all_new] + ["no tools"] * 14)
    await flows.build(ctx, cfg(llm))
    assert "function render" in ctx.state.app_html
    assert any("default table view" in e["label"] for e in p.events)


async def _built():
    ctx, box, p = make()
    llm = ScriptedLLM(
        DESIGN_TURNS
        + [save_all_new, [("write_app", {"html": GOOD_APP})], [("finish", {"summary": "ok"})]]
    )
    await flows.build(ctx, cfg(llm))
    return ctx.state, p


async def test_sync_with_nothing_new_makes_no_llm_call():
    state, p = await _built()
    ctx, _, _ = make("2026-10-17T00:00:00Z", state=state, persister=p)
    llm = ScriptedLLM([])
    assert await flows.sync(ctx, cfg(llm)) == "No new emails"
    assert llm.calls == [] and state.last_synced_at == ctx.now


async def test_sync_processes_new_messages_once():
    state, p = await _built()
    ctx, _, _ = make("2026-10-22T00:00:00Z", state=state, persister=p)
    seen_inputs = []

    def turn(messages):
        seen_inputs.append(messages[1]["content"])
        return save_all_new(messages)

    llm = ScriptedLLM([turn])
    await flows.sync(ctx, cfg(llm))
    assert len(seen_inputs) == 1
    assert seen_inputs[0].count('new="true"') == 1  # only the delivered message
    assert len(p.processed) == 8
    # Sync again at the same time: the overlap window finds it, but it's processed.
    ctx2, _, _ = make("2026-10-22T00:30:00Z", state=state, persister=p)
    llm2 = ScriptedLLM([])
    assert await flows.sync(ctx2, cfg(llm2)) == "No new emails"


async def test_edit_failure_restores_snapshot():
    state, p = await _built()
    before = (dict(state.data), state.guide, state.app_html)
    ctx, _, _ = make("2026-10-17T00:00:00Z", state=state, persister=p)
    llm = ScriptedLLM(
        [[("write_guide", {"text": "# Purpose\nchanged\n# Learned\n"})]]
        + [[("read_thread", {"thread_id": "nope"})]] * 3
    )
    with pytest.raises(PhaseFailed):
        await flows.edit(ctx, cfg(llm), "change it", [])
    assert (state.data, state.guide, state.app_html) == before


async def test_edit_with_backfill_rereads_known_threads():
    state, p = await _built()
    ctx, _, _ = make("2026-10-17T00:00:00Z", state=state, persister=p)
    inputs = []

    def reread(messages):
        inputs.append(messages[1]["content"])
        return [("finish", {"summary": "No changes"})]

    llm = ScriptedLLM(
        [
            [("write_guide", {"text": GUIDE + "- new field"}), ("request_backfill", {})],
            [("finish", {"summary": "Added a field."})],
            reread,
        ]
    )
    assert await flows.edit(ctx, cfg(llm), "add a field", []) == "Added a field."
    assert "re-read" in inputs[0] and inputs[0].count("<thread ") == 6
