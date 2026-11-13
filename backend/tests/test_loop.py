"""Agent loop with a scripted LLM: multi-tool turns, error feedback, aborts, trimming."""

import pytest

from app.agent.context import BudgetExceeded, MemoryPersister, RunContext, WorkspaceState
from app.agent.loop import KEEP_THREADS, PhaseFailed, run_agent
from app.agent.tools import tools_for
from app.mail.fake import FakeMailbox
from tests.helpers import SMALL_MAILBOX, ScriptedLLM, dt, tool_results


def make_ctx(max_usd=1e9, phase="process"):
    box = FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-30T00:00:00Z"))
    p = MemoryPersister(max_usd=max_usd)
    ctx = RunContext(
        state=WorkspaceState(prompt="p"),
        mailbox=box,
        persister=p,
        run_id="t",
        now=dt("2026-10-30T00:00:00Z"),
    )
    ctx.phase = phase
    return ctx, box, p


async def run(ctx, llm, phase="edit", max_steps=10):
    return await run_agent(
        llm=llm, model="m", system="s", user="u", tools=tools_for(phase), ctx=ctx, max_steps=max_steps
    )


async def test_multi_tool_turn_then_finish():
    ctx, box, p = make_ctx()
    hits = await box.search("A-1001")
    tid = hits[0].thread_id
    llm = ScriptedLLM(
        [
            [("search_mail", {"query": "A-1001"}), ("read_thread", {"thread_id": tid})],
            lambda msgs: [
                (
                    "save_records",
                    {
                        "record_type": "order",
                        "records": [
                            {
                                "id": "a-1001",
                                "fields": {"item": "Desk lamp"},
                                "source_message_ids": [
                                    tool_results(msgs)[-1]["messages"][0]["message_id"]
                                ],
                            }
                        ],
                    },
                )
            ],
            [("finish", {"summary": "1 order added"})],
        ]
    )
    result = await run(ctx, llm)
    assert result.finished and result.summary == "1 order added" and result.steps == 3
    assert ctx.state.data["order"]["a-1001"]["item"] == "Desk lamp"
    assert [e["label"] for e in p.events] == [
        "Searching mail",
        "Reading a thread",
        "Saved 1 order record (1 new)",
    ]
    assert p.input_tokens == 300


async def test_tool_error_is_fed_back_and_unknown_source_rejected():
    ctx, _, _ = make_ctx()
    bad = {"record_type": "order", "records": [{"id": "x", "fields": {}, "source_message_ids": ["zz"]}]}
    llm = ScriptedLLM([[("save_records", bad)], [("finish", {"summary": "ok"})]])
    await run(ctx, llm)
    feedback = tool_results(llm.calls[1])[0]
    assert "received in this run" in feedback["error"]
    assert ctx.state.data == {}


async def test_three_consecutive_errors_fail_the_phase():
    ctx, _, _ = make_ctx()
    llm = ScriptedLLM([[("read_thread", {"thread_id": "nope"})]] * 3)
    with pytest.raises(PhaseFailed, match="3 times"):
        await run(ctx, llm)


async def test_invalid_json_arguments_are_an_error():
    ctx, _, _ = make_ctx()

    class BadJson(ScriptedLLM):
        async def chat(self, model, messages, tools):
            reply = await super().chat(model, messages, tools)
            if reply.tool_calls and reply.tool_calls[0].name == "search_mail":
                reply.tool_calls[0].arguments = "{not json"
            return reply

    llm = BadJson([[("search_mail", {})], [("finish", {"summary": "x"})]])
    await run(ctx, llm)
    assert "not valid JSON" in tool_results(llm.calls[1])[0]["error"]


async def test_step_limit_sends_out_of_steps_then_fails():
    ctx, _, _ = make_ctx()
    llm = ScriptedLLM(["thinking...", "still thinking", "nope"])
    with pytest.raises(PhaseFailed, match="out of steps"):
        await run(ctx, llm, max_steps=2)
    assert "out of steps" in llm.calls[-1][-1]["content"]


async def test_step_limit_recovers_when_finish_called():
    ctx, _, _ = make_ctx()
    llm = ScriptedLLM(["a", "b", [("finish", {"summary": "done"})]])
    result = await run(ctx, llm, max_steps=2)
    assert result.finished


async def test_context_trimming_keeps_recent_threads():
    ctx, box, _ = make_ctx()
    hits = await box.search("", max_results=50)
    ids = [h.thread_id for h in hits]
    ctx.known_threads.update(ids)
    reads = [[("read_thread", {"thread_id": ids[i % len(ids)]})] for i in range(KEEP_THREADS + 2)]
    llm = ScriptedLLM(reads + [[("finish", {"summary": "x"})]])
    await run(ctx, llm, max_steps=20)
    last = llm.calls[-1]
    tool_msgs = [m for m in last if m["role"] == "tool"]
    dropped = [m for m in tool_msgs if "already read, content dropped" in m["content"]]
    assert len(dropped) == 2
    assert all("_thread_id" not in m for m in last)


async def test_budget_abort():
    ctx, _, _ = make_ctx(max_usd=0.0000001)
    llm = ScriptedLLM([[("finish", {"summary": "x"})]])
    with pytest.raises(BudgetExceeded):
        await run(ctx, llm)


async def test_sync_may_only_change_learned_section():
    ctx, _, _ = make_ctx(phase="process")
    ctx.state.guide = "# Purpose\nA\n\n# Learned\n"
    llm = ScriptedLLM(
        [
            [("write_guide", {"text": "# Purpose\nB\n\n# Learned\n"})],
            [("write_guide", {"text": "# Purpose\nA\n\n# Learned\n- 2026-10-30: new rule"})],
            [("finish", {"summary": "x"})],
        ]
    )
    await run_agent(
        llm=llm, model="m", system="s", user="u", tools=tools_for("process"), ctx=ctx, max_steps=5
    )
    assert "only change" in tool_results(llm.calls[1])[0]["error"]
    assert ctx.state.guide.endswith("new rule")
