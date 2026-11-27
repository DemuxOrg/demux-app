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


async def test_ask_user_uses_recommended_options_without_answers():
    ctx, p = _ctx()
    out = await TOOLS["ask_user"].handler(ctx, QUESTIONS)
    assert [a["answer"] for a in out.result["answers"]] == ["No", "All"]
    assert p.setup["questions_state"] == "auto" or p.setup["questions_state"] == "timed_out"
    assert [q["id"] for q in p.setup["questions"]] == ["q1", "q2"]
    assert ctx.state.config["clarifications"][0] == {
        "question": "Should e-book loans count?",
        "answer": "No",
    }
    with pytest.raises(ToolError, match="once"):
        await TOOLS["ask_user"].handler(ctx, QUESTIONS)


async def test_ask_user_returns_the_users_answers():
    ctx, p = _ctx(wait=5)
    p.setup["answers"] = {"q1": "Yes", "q2": "Other: Central and North"}
    out = await TOOLS["ask_user"].handler(ctx, QUESTIONS)
    assert [a["answer"] for a in out.result["answers"]] == ["Yes", "Other: Central and North"]
    assert all(a["from"] == "user" for a in out.result["answers"])
    assert p.setup["questions_state"] == "answered"


async def test_ask_user_takes_up_to_five_questions_for_a_vague_request():
    ctx, p = _ctx()
    many = {
        "questions": [
            {"question": f"Question {i}?", "options": ["a", "b"], "recommended": 1}
            for i in range(5)
        ]
    }
    out = await TOOLS["ask_user"].handler(ctx, many)
    assert [q["id"] for q in p.setup["questions"]] == ["q1", "q2", "q3", "q4", "q5"]
    assert len(out.result["answers"]) == 5


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


async def test_setup_api_answers(client, session):
    ws = (await client.post(URL, json=BODY)).json()
    detail = (await client.get(f"{URL}/{ws['id']}")).json()
    setup = detail["active_run"]["setup"]
    assert setup == {"questions_state": "deciding", "questions": [], "answered": False}

    # Nothing to answer yet.
    early = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q1": "Yes"}})
    assert early.status_code == 409

    run = await _build_run(session, ws["id"])
    run.input = {
        **run.input,
        "questions": [{"id": "q1", "question": "E-books?", "options": ["Yes", "No"],
                       "recommended": 1}],
        "questions_state": "asking",
    }  # fmt: skip
    await session.flush()

    bad = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q9": "Yes"}})
    assert bad.status_code == 422
    empty = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {}})
    assert empty.status_code == 422
    ok = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q1": "Yes"}})
    assert ok.status_code == 200 and ok.json()["setup"]["answered"] is True
    await session.refresh(run)
    assert run.input["answers"] == {"q1": "Yes"}


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
