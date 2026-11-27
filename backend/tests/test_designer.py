"""The interface designer: the UI model designs and writes every studio (v3) app, in
builds and in edits; the main agent only hands it the facts or the change."""

import json

import pytest

from app.agent import flows
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.designer import Designer, designer_from_settings, extract_app
from app.agent.llm import CallOptions, LLMError, LLMReply, MeteredLLM
from app.agent.prompts import INTERFACE, edit_input, interface_change_input, interface_input
from app.agent.shell import app_runtime, studio_app
from app.agent.tools import TOOLS, tools_for
from app.mail.fake import FakeMailbox
from tests.helpers import GOOD_STUDIO_ANSWER, GOOD_STUDIO_JSX, SMALL_MAILBOX, PhaseLLM, dt

DATA = {
    "order": {
        "o-1": {"item": "Desk lamp", "status": "shipped", "_sources": [{"thread_id": "t1"}]},
    }
}


def _ctx(app_html=None):
    p = MemoryPersister()
    state = WorkspaceState(prompt="track orders", name="Orders", data=json.loads(json.dumps(DATA)))
    state.guide = "# Purpose\nOrders.\n"
    state.app_html = app_html
    p.state = state
    ctx = RunContext(
        state=state,
        mailbox=FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-16T00:00:00Z")),
        persister=p,
        run_id="t",
    )
    ctx.phase = "app"
    return ctx, p


class Answers:
    """A UI model that answers from a list; records the options it was called with."""

    def __init__(self, *answers, truncated=()):
        self.answers = list(answers)
        self.truncated = set(truncated)
        self.calls = []

    async def chat(self, model, messages, tools, options=None):
        self.calls.append(
            {
                "model": model,
                "messages": json.loads(json.dumps(messages)),
                "tools": tools,
                "options": options,
            }
        )
        n = len(self.calls)
        text = self.answers.pop(0)
        return LLMReply(text, [], 1000, 2000, 5, {}, model, truncated=n in self.truncated)


# ------------------------------------------------------------------ answers


@pytest.mark.parametrize(
    "answer",
    [
        f"```jsx\n{GOOD_STUDIO_JSX}\n```",
        f"Sure! Here you go:\n\n```tsx\n{GOOD_STUDIO_JSX}\n```\n\nIt shows every record.",
        f'<script type="text/jsx">{GOOD_STUDIO_JSX}</script>',
        GOOD_STUDIO_JSX,
        "```jsx\nimport React, { useState } from 'react';\nimport { BarChart } from \"recharts\";\n"
        + GOOD_STUDIO_JSX.replace("function App", "export default function App")
        + "\n```",
        f"```jsx\n{GOOD_STUDIO_JSX}\nexport default App;\n```",
    ],
)
def test_extract_app_takes_the_code_and_drops_import_habits(answer):
    code = extract_app(answer)
    assert code is not None and code.startswith("function App({ data })")
    assert "import" not in code and "export" not in code


def test_extract_app_ignores_inline_reasoning():
    draft = "function App({ data }) { return <p>draft</p>; " + "x;" * 500 + "}"
    answer = (
        f"<think>First a draft:\n```jsx\n{draft}\n```\n</think>\n```jsx\n{GOOD_STUDIO_JSX}\n```"
    )
    assert extract_app(answer) == GOOD_STUDIO_JSX.strip()


def test_extract_app_finds_nothing_in_prose():
    assert extract_app("I would build a board with three columns.") is None
    assert extract_app(None) is None


# ------------------------------------------------------------------ design


async def test_design_saves_a_checked_studio_app_and_bills_it():
    ctx, p = _ctx()
    llm = Answers(GOOD_STUDIO_ANSWER)
    options = CallOptions(max_tokens=24000, timeout_s=300, fallback_model="")
    designer = Designer(llm=llm, model="zai-org/GLM-5.2:deepinfra", options=options)
    assert await designer.design(ctx) == []
    assert ctx.state.app_html == studio_app(GOOD_STUDIO_JSX) and ctx.app_written
    assert app_runtime(ctx.state.app_html) == "v3"
    call = llm.calls[0]
    assert call["model"] == "zai-org/GLM-5.2:deepinfra" and call["tools"] == []
    assert call["options"] is options
    assert call["messages"][0]["content"] == INTERFACE
    assert "<request>\ntrack orders\n</request>" in call["messages"][1]["content"]
    assert p.input_tokens == 1000 and p.output_tokens == 2000


async def test_design_asks_again_when_the_answer_was_cut_or_has_no_code():
    ctx, _ = _ctx()
    llm = Answers(GOOD_STUDIO_ANSWER, "Here is my plan.", GOOD_STUDIO_ANSWER, truncated={1})
    assert await Designer(llm=llm, model="ui").design(ctx) == []
    assert "cut off" in llm.calls[1]["messages"][-1]["content"]
    assert "no app found" in llm.calls[2]["messages"][-1]["content"]


async def test_design_gives_up_after_max_attempts_and_keeps_the_app():
    ctx, _ = _ctx(app_html="<p>old</p>")
    llm = Answers(*["no code"] * 2)
    problems = await Designer(llm=llm, model="ui", max_attempts=2).design(ctx)
    assert problems and ctx.state.app_html == "<p>old</p>" and not ctx.app_written


def test_designer_from_settings_uses_the_ui_model(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "UI_MODEL", "zai-org/GLM-5.2:novita")
    monkeypatch.setattr(settings, "UI_FALLBACK_MODEL", "")
    d = designer_from_settings(Answers())
    assert d.model == "zai-org/GLM-5.2:novita"
    assert d.options.fallback_model == "" and d.options.max_tokens == settings.UI_MAX_TOKENS


async def test_metered_llm_passes_the_options_through():
    inner = Answers(GOOD_STUDIO_ANSWER)
    opts = CallOptions(max_tokens=123)
    await MeteredLLM(inner).chat("ui", [{"role": "user", "content": "x"}], [], options=opts)
    assert inner.calls[0]["options"] is opts


# ------------------------------------------------------------------ inputs


def test_the_designer_gets_facts_and_a_data_sample():
    many = {"order": {f"o-{i}": {"item": f"thing {i}"} for i in range(20)}}
    text = interface_input("Orders", "track orders", "# Purpose\nOrders.", many)
    assert "Records so far: order: 20" in text
    assert "thing 5" in text and "thing 6" not in text  # 6 per type


def test_a_change_brief_holds_the_current_app_and_the_users_words():
    app = studio_app(GOOD_STUDIO_JSX)
    text = interface_change_input(
        "Orders", "p", "g", DATA, None, current_app=app, change="dark theme", user_message="go dark"
    )
    assert GOOD_STUDIO_JSX.strip() in text and "<change>\ndark theme\n</change>" in text
    assert "<user_message>\ngo dark\n</user_message>" in text
    old = interface_change_input("O", "p", "g", {}, None, current_app="<p>kit</p>", change="x")
    assert "no longer available" in old


def test_the_edit_agent_never_sees_or_writes_interface_code():
    names = [t.name for t in tools_for("edit")]
    assert "change_interface" in names and "write_app" not in names
    text = edit_input("x", "p", "g", [], {}, "<script>secret app code</script>", [], 10_000)
    assert "secret app code" not in text and "<app>present" in text


# ------------------------------------------------------------------ edits


async def test_change_interface_hands_the_change_to_the_designer():
    ctx, _ = _ctx(app_html=studio_app(GOOD_STUDIO_JSX))
    llm = Answers(GOOD_STUDIO_ANSWER.replace("p-6 font-sans", "p-8 font-serif"))
    ctx.designer = Designer(llm=llm, model="ui")
    ctx.user_message = "make it feel like a magazine"
    out = await TOOLS["change_interface"].handler(ctx, {"change": "Editorial look, serif type"})
    assert out.result == {"ok": True}
    assert "font-serif" in ctx.state.app_html
    brief = llm.calls[0]["messages"][1]["content"]
    assert "make it feel like a magazine" in brief and "Editorial look" in brief


async def test_change_interface_reports_a_designer_outage_to_the_agent():
    class Down:
        async def chat(self, *a, **k):
            raise LLMError("provider down", "http_503")

    ctx, _ = _ctx(app_html="<p>old</p>")
    ctx.designer = Designer(llm=Down(), model="ui")
    out = await TOOLS["change_interface"].handler(ctx, {"change": "x"})
    assert out.result["ok"] is False and "unavailable" in out.result["error"]
    assert ctx.state.app_html == "<p>old</p>"


async def test_edit_flow_routes_interface_changes_to_the_ui_model():
    ctx, _ = _ctx(app_html=studio_app(GOOD_STUDIO_JSX))
    ctx.phase = "edit"
    new = GOOD_STUDIO_ANSWER.replace("p-6", "p-10")
    llm = PhaseLLM(
        edit=[
            [("change_interface", {"change": "more room around everything"})],
            [("finish", {"summary": "Added more space."})],
        ],
        app=[new],
    )
    cfg = flows.FlowConfig(llm=llm, build_model="b", sync_model="s")
    summary = await flows.edit(ctx, cfg, "it feels cramped", [])
    assert summary == "Added more space." and "p-10" in ctx.state.app_html
    assert llm.phases == ["edit", "app", "edit"]
