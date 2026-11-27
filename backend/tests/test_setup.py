"""Setup with the user during a build: the clarifying questions (ask_user), waiting for
the answers, and the setup API (frontend/theme.md §7.10)."""

import pytest

from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.prompts import edit_input, interface_input
from app.agent.tools import TOOLS, ToolError
from app.mail.fake import FakeMailbox
from app.models import Run, RunKind, RunStatus
from tests.helpers import SMALL_MAILBOX, dt

URL = "/api/v1/workspaces"
BODY = {"prompt": "Track invoices from my email"}

QUESTIONS = {
    "questions": [
        {"question": "Should e-book loans count?", "options": ["Yes", "No"], "recommended": 1},
        {"question": "Which branches?", "options": ["All", "Central only"], "recommended": 0},
    ]
}


def _ctx(wait: float = 0.0) -> tuple[RunContext, MemoryPersister]:
    persister = MemoryPersister()
    state = WorkspaceState(prompt="p")
    persister.state = state
    ctx = RunContext(
        state=state,
        mailbox=FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-30T00:00:00Z")),
        persister=persister,
        run_id="t",
        setup_wait=wait,
    )
    ctx.phase = "design"
    return ctx, persister


# ------------------------------------------------------------------ tools


async def test_ask_user_returns_at_once_and_get_answers_falls_back():
    """ask_user doesn't wait; get_answers gives the recommended option per question the
    user left unanswered (here: no answers and no wait)."""
    ctx, p = _ctx()
    out = await TOOLS["ask_user"].handler(ctx, QUESTIONS)
    assert out.result["ok"] and "get_answers" in out.result["note"]
    assert p.setup["questions_state"] == "asking" and "questions_at" in p.setup
    assert [q["id"] for q in p.setup["questions"]] == ["q1", "q2"]
    with pytest.raises(ToolError, match="once"):
        await TOOLS["ask_user"].handler(ctx, QUESTIONS)
    with pytest.raises(ToolError, match="get_answers"):
        await TOOLS["write_guide"].handler(ctx, {"text": "# Purpose\nx"})

    got = await TOOLS["get_answers"].handler(ctx, {})
    assert [a["answer"] for a in got.result["answers"]] == ["No", "All"]
    assert all(a["from"] == "recommended (no answer)" for a in got.result["answers"])
    assert p.setup["questions_state"] == "timed_out"
    assert ctx.state.config["clarifications"][0] == {
        "question": "Should e-book loans count?",
        "answer": "No",
    }
    await TOOLS["write_guide"].handler(ctx, {"text": "# Purpose\nx"})  # now allowed


async def test_get_answers_returns_once_all_are_answered():
    ctx, p = _ctx(wait=5)
    await TOOLS["ask_user"].handler(ctx, QUESTIONS)
    p.setup["answers"] = {"q1": "Yes", "q2": "Other: Central and North"}
    out = await TOOLS["get_answers"].handler(ctx, {})
    assert [a["answer"] for a in out.result["answers"]] == ["Yes", "Other: Central and North"]
    assert all(a["from"] == "user" for a in out.result["answers"])
    assert p.setup["questions_state"] == "answered"


async def test_get_answers_waits_while_the_user_keeps_answering(monkeypatch):
    """The idle deadline restarts at each answer: a user answering one question at a
    time is never cut off, a user who stops is."""
    import asyncio
    from datetime import UTC, datetime

    from app.agent import tools

    monkeypatch.setattr(tools, "SETUP_POLL_SECONDS", 0.05)
    ctx, p = _ctx(wait=0.4)
    await TOOLS["ask_user"].handler(ctx, QUESTIONS)

    async def answer_slowly():
        await asyncio.sleep(0.3)  # within the 0.4 s idle window
        p.setup["answers"] = {"q1": "Yes"}
        p.setup["answered_at"] = {"q1": datetime.now(UTC).isoformat()}
        await asyncio.sleep(0.3)  # 0.6 s after asking, but 0.3 s after the last answer
        p.setup["answers"] = {"q1": "Yes", "q2": "Central only"}

    task = asyncio.create_task(answer_slowly())
    out = await TOOLS["get_answers"].handler(ctx, {})
    await task
    assert [a["answer"] for a in out.result["answers"]] == ["Yes", "Central only"]
    assert p.setup["questions_state"] == "answered"


async def test_get_answers_wait_is_capped_even_if_answers_keep_arriving(monkeypatch):
    """Re-sending one answer restarts the idle deadline, but the whole wait is capped
    (SETUP_MAX_WAITS idle windows), so a build can't hold a worker slot forever."""
    import asyncio
    import time
    from datetime import UTC, datetime

    from app.agent import tools

    monkeypatch.setattr(tools, "SETUP_POLL_SECONDS", 0.02)
    monkeypatch.setattr(tools, "SETUP_MAX_WAITS", 3)
    ctx, p = _ctx(wait=0.2)
    await TOOLS["ask_user"].handler(ctx, QUESTIONS)

    async def keep_answering_q1():
        while True:  # well within the idle window each time, q2 never answered
            p.setup["answers"] = {"q1": "Yes"}
            p.setup["answered_at"] = {"q1": datetime.now(UTC).isoformat()}
            await asyncio.sleep(0.05)

    task = asyncio.create_task(keep_answering_q1())
    started = time.monotonic()
    try:
        out = await asyncio.wait_for(TOOLS["get_answers"].handler(ctx, {}), timeout=5)
    finally:
        task.cancel()
    assert time.monotonic() - started < 1.5  # cap: 3 x 0.2 s
    assert [a["from"] for a in out.result["answers"]] == ["user", "recommended (no answer)"]
    assert p.setup["questions_state"] == "timed_out"


async def test_ask_user_takes_up_to_five_questions_for_a_vague_request():
    ctx, p = _ctx()
    many = {
        "questions": [
            {"question": f"Question {i}?", "options": ["a", "b"], "recommended": 1}
            for i in range(5)
        ]
    }
    await TOOLS["ask_user"].handler(ctx, many)
    assert [q["id"] for q in p.setup["questions"]] == ["q1", "q2", "q3", "q4", "q5"]
    out = await TOOLS["get_answers"].handler(ctx, {})
    assert len(out.result["answers"]) == 5


async def test_get_answers_needs_a_question():
    ctx, _ = _ctx()
    with pytest.raises(ToolError, match="asked nothing"):
        await TOOLS["get_answers"].handler(ctx, {})


@pytest.mark.parametrize(
    "args",
    [
        {"questions": []},
        {"questions": [{"question": "x", "options": ["only one"], "recommended": 0}]},
        {"questions": [{"question": "q", "options": ["a", "b"], "recommended": 0}] * 6},
    ],
)
async def test_ask_user_validates(args):
    ctx, _ = _ctx()
    with pytest.raises(ToolError):
        await TOOLS["ask_user"].handler(ctx, args)


@pytest.mark.parametrize(
    "question",
    [
        {"question": "Which colours do you like?", "options": ["Violet", "Teal"]},
        {"question": "Which look?", "options": ["Light mode", "Dark mode"]},
        {"question": "Pick a theme for your workspace", "options": ["Calm", "Bold"]},
    ],
)
async def test_ask_user_refuses_questions_about_the_look(question):
    ctx, p = _ctx()
    with pytest.raises(ToolError, match="colours"):
        await TOOLS["ask_user"].handler(ctx, {"questions": [{**question, "recommended": 0}]})
    assert "questions" not in p.setup and not ctx.asked_user


def test_interface_designer_sees_the_clarifications():
    config = {"clarifications": [{"question": "E-books?", "answer": "No"}]}
    text = interface_input("Loans", "p", "g", {}, config)
    assert "<name>Loans</name>" in text
    assert "<clarifications>\n- E-books? → No\n</clarifications>" in text
    assert text.index("<clarifications>") < text.index("<guide>")
    assert "<clarifications>" not in interface_input("Loans", "p", "g", {})


def test_edit_sees_the_clarifications():
    text = edit_input(
        "x", "p", "g", [], {}, None, [], 10_000,
        config={"clarifications": [{"question": "E-books?", "answer": "No"}]},
    )  # fmt: skip
    assert "<clarifications>\n- E-books? → No\n</clarifications>" in text


# ------------------------------------------------------------------ API


async def _build_run(session, ws_id) -> Run:
    from sqlalchemy import select

    return await session.scalar(
        select(Run).where(Run.workspace_id == ws_id, Run.kind == RunKind.BUILD)
    )


async def test_setup_api_answers_one_at_a_time(client, session):
    ws = (await client.post(URL, json=BODY)).json()
    detail = (await client.get(f"{URL}/{ws['id']}")).json()
    setup = detail["active_run"]["setup"]
    assert setup == {
        "questions_state": "deciding",
        "questions": [],
        "answered": False,
        "answered_ids": [],
        "look_state": "asking",
        "look_from_prompt": False,
    }

    # Nothing to answer yet.
    early = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q1": "Yes"}})
    assert early.status_code == 409

    run = await _build_run(session, ws["id"])
    run.input = {
        **run.input,
        "questions": [
            {"id": "q1", "question": "E-books?", "options": ["Yes", "No"], "recommended": 1},
            {"id": "q2", "question": "Branches?", "options": ["All", "One"], "recommended": 0},
        ],
        "questions_state": "asking",
    }
    await session.flush()

    bad = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q9": "Yes"}})
    assert bad.status_code == 422
    empty = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {}})
    assert empty.status_code == 422
    nothing = await client.post(f"{URL}/{ws['id']}/setup", json={})
    assert nothing.status_code == 422

    # One answer per request; they merge, each with its time.
    first = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q1": "Yes"}})
    assert first.status_code == 200 and first.json()["setup"]["answered_ids"] == ["q1"]
    second = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q2": "One"}})
    assert second.json()["setup"]["answered_ids"] == ["q1", "q2"]
    await session.refresh(run)
    assert run.input["answers"] == {"q1": "Yes", "q2": "One"}
    assert set(run.input["answered_at"]) == {"q1", "q2"}


async def test_setup_api_look(client, session):
    ws = (await client.post(URL, json=BODY)).json()
    ok = await client.post(f"{URL}/{ws['id']}/setup", json={"look": "Navy and gold"})
    setup = ok.json()["setup"]
    assert ok.status_code == 200 and setup["look_state"] == "answered"
    run = await _build_run(session, ws["id"])
    await session.refresh(run)
    assert run.input["look"] == "Navy and gold"
    again = await client.post(f"{URL}/{ws['id']}/setup", json={"look": "Dark"})
    assert again.status_code == 409


async def test_a_prompt_that_names_a_look_skips_the_moment(client):
    ws = (await client.post(URL, json={"prompt": "Track my bills in teal"})).json()
    setup = (await client.get(f"{URL}/{ws['id']}")).json()["active_run"]["setup"]
    assert setup["look_state"] == "from_prompt" and setup["look_from_prompt"] is True
    refused = await client.post(f"{URL}/{ws['id']}/setup", json={"look": "Dark"})
    assert refused.status_code == 409


async def test_app_is_the_preview_until_one_is_saved(client, session):
    from app.agent.default_app import DEFAULT_APP
    from app.models import Workspace

    ws = (await client.post(URL, json=BODY)).json()
    app = (await client.get(f"{URL}/{ws['id']}/app")).json()
    assert app["provisional"] is True and app["html"] == DEFAULT_APP and app["runtime"] == "v3"
    row = await session.get(Workspace, ws["id"])
    row.app_html = DEFAULT_APP.replace("TypeList", "Lists")
    await session.flush()
    saved = (await client.get(f"{URL}/{ws['id']}/app")).json()
    assert saved["provisional"] is False


async def test_setup_api_isolation_and_finished_builds(client, other_client, session):
    ws = (await client.post(URL, json=BODY)).json()
    run = await _build_run(session, ws["id"])
    run.input = {
        **run.input,
        "questions": [{"id": "q1", "question": "E-books?", "options": ["Yes", "No"],
                       "recommended": 1}],
        "questions_state": "asking",
    }  # fmt: skip
    await session.flush()
    answer = {"answers": {"q1": "No"}}
    other = await other_client.post(f"{URL}/{ws['id']}/setup", json=answer)
    assert other.status_code == 404
    await session.execute(Run.__table__.update().values(status=RunStatus.DONE.value))
    done = await client.post(f"{URL}/{ws['id']}/setup", json=answer)
    assert done.status_code == 409
