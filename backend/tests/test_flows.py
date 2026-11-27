"""Flows with a scripted LLM and the fake mailbox (memory persister)."""

import re

import pytest

from app.agent import flows
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.default_app import DEFAULT_APP
from app.agent.loop import PhaseFailed
from app.agent.shell import studio_app
from app.mail.fake import FakeMailbox
from tests.helpers import (
    GOOD_STUDIO_ANSWER,
    GOOD_STUDIO_JSX,
    SMALL_MAILBOX,
    PhaseLLM,
    ScriptedLLM,
    dt,
    tool_results,
)

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
    [
        ("write_guide", {"text": GUIDE}),
        ("set_queries", {"queries": ["order"]}),
    ],
    [("finish", {"summary": "Tracks orders."})],
]


APP_TURNS = [GOOD_STUDIO_ANSWER]
GOOD_STUDIO_APP = studio_app(GOOD_STUDIO_JSX)


def build_llm(**over):
    turns = {"design": DESIGN_TURNS, "process": [save_all_new], "app": APP_TURNS}
    turns.update(over)
    return PhaseLLM(**turns)


async def test_build_happy_path():
    ctx, _, p = make()
    summary = await flows.build(ctx, cfg(build_llm()))
    assert "Built from 6 threads" in summary
    assert len(ctx.state.data["order"]) >= 3
    assert ctx.state.app_html == GOOD_STUDIO_APP and ctx.state.last_synced_at == ctx.now
    assert len(p.processed) == 7  # every message of the 6 visible threads
    assert p.snapshots, "build takes a snapshot first"
    labels = [e["label"] for e in p.events]
    assert "Reading your emails (1 of 1 batches)" in labels


async def test_build_runs_batches_in_parallel_and_app_alongside():
    ctx, _, p = make()
    llm = build_llm()
    await flows.build(ctx, cfg(llm, batch=2))
    assert len(llm.calls_for("process")) == 3  # 6 threads in batches of 2, one turn each
    assert len(ctx.state.data["order"]) >= 3 and len(p.processed) == 7
    # The app phase started before the last batch finished.
    assert llm.phases.index("app") < len(llm.phases) - 1 - llm.phases[::-1].index("process")


async def test_batches_are_cut_by_size():
    ctx, box, _ = make()
    threads = [await box.get_thread(s.thread_id) for s in await box.search("", 50)]
    config = cfg(ScriptedLLM([]), batch=50)
    config.batch_max_chars = 600
    ids = {m.message_id for t in threads for m in t.messages}
    batches = flows._make_batches(ctx, config, threads, ids)
    assert len(batches) > 1 and sum(len(b) for b, _ in batches) == len(threads)


async def test_design_budget_stops_endless_reading():
    ctx, box, _ = make()
    tid = (await box.search("A-1001"))[0].thread_id
    reads = [("read_thread", {"thread_id": tid})] * 12
    llm = build_llm(design=[[("search_mail", {"query": "order"})], reads, *DESIGN_TURNS[1:]])
    await flows.build(ctx, cfg(llm))
    errors = [r for r in tool_results(llm.calls_for("design")[2]) if "error" in r]
    assert len(errors) == 2 and "budget" in errors[0]["error"]


async def test_build_cannot_build():
    ctx, _, _ = make()
    llm = build_llm(
        design=[[("finish", {"summary": "CANNOT_BUILD: your step counts are not in email."})]]
    )
    with pytest.raises(flows.CannotBuild, match="step counts"):
        await flows.build(ctx, cfg(llm))


async def test_design_finish_without_guide_is_rejected_then_fails():
    ctx, _, _ = make()
    llm = build_llm(design=[[("finish", {"summary": "done"})]] * 3)
    with pytest.raises(PhaseFailed, match="3 times"):
        await flows.build(ctx, cfg(llm))
    assert "write_guide" in tool_results(llm.calls[1])[0]["error"]


async def test_failed_batch_is_skipped_and_build_continues():
    ctx, _, p = make()
    bad = [("read_thread", {"thread_id": "nope"})]
    n = {"calls": 0}

    def flaky(messages):
        # The first batch to start fails on every turn of both attempts; others succeed.
        first = '<thread id="' + first_tid + '"' in messages[1]["content"]
        n["calls"] += first
        return bad if first else save_all_new(messages)

    threads = sorted(
        [await ctx.mailbox.get_thread(s.thread_id) for s in await ctx.mailbox.search("order", 50)],
        key=lambda t: t.messages[-1].date,
    )
    first_tid = threads[0].thread_id
    await flows.build(ctx, cfg(build_llm(process=[flaky]), batch=3))
    assert n["calls"] == 6  # two attempts × three consecutive errors
    assert any("Skipped batch 1" in e["label"] for e in p.events)
    assert ctx.state.data["order"]


async def test_designer_failure_falls_back_to_default_app():
    ctx, _, p = make()
    llm = build_llm(app=["I would rather describe it in words."] * 3)
    await flows.build(ctx, cfg(llm))
    assert ctx.state.app_html == DEFAULT_APP
    assert len(llm.calls_for("app")) == 3  # first design + two fixes
    assert any("simple list view" in e["label"] for e in p.events)


async def test_app_is_fixed_against_the_real_data_after_reading():
    ctx, _, p = make()
    # Fine while the data is still empty, crashes once records exist.
    broken = GOOD_STUDIO_ANSWER.replace("records(data, t)", "data.missing.x")
    llm = build_llm(app=[broken, GOOD_STUDIO_ANSWER])
    await flows.build(ctx, cfg(llm))
    assert ctx.state.app_html == GOOD_STUDIO_APP
    second = llm.calls_for("app")[1][-1]["content"]
    assert "<current_app>" in second and "fails these checks" in second
    assert "Adjusting the interface to your data" in [e["label"] for e in p.events]


async def test_designer_fixes_a_rejected_app():
    ctx, _, p = make()
    broken = GOOD_STUDIO_ANSWER.replace("types(data)", "types(data.missing.x)")
    llm = build_llm(app=[broken, GOOD_STUDIO_ANSWER])
    await flows.build(ctx, cfg(llm))
    assert ctx.state.app_html == GOOD_STUDIO_APP
    fix_request = llm.calls_for("app")[1][-1]["content"]
    assert fix_request.startswith("The app was rejected") and "render error" in fix_request
    labels = [e["label"] for e in p.events]
    assert "Interface check failed, fixing" in labels and "Interface ready" in labels


async def _built():
    ctx, box, p = make()
    await flows.build(ctx, cfg(build_llm()))
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
