"""Setup with the user during a build: clarifying questions (ask_user), layout options
(propose_views), waiting for the answers, and the setup API (frontend/theme.md §7.10)."""

import pytest

from app.agent import flows
from app.agent.context import MemoryPersister, RunContext, WorkspaceState
from app.agent.prompts import app_input, edit_input
from app.agent.tools import TOOLS, ToolError
from app.mail.fake import FakeMailbox
from app.models import Run, RunKind, RunStatus, Workspace
from tests.helpers import SMALL_MAILBOX, dt

URL = "/api/v1/workspaces"
BODY = {"prompt": "Track invoices from my email"}

QUESTIONS = {
    "questions": [
        {"question": "Should e-book loans count?", "options": ["Yes", "No"], "recommended": 1},
        {"question": "Which branches?", "options": ["All", "Central only"], "recommended": 0},
    ]
}
VIEWS = {
    "options": [
        {
            "block": "Board",
            "title": "Board by status",
            "description": "status",
            "recommended": True,
        },
        {"block": "Timeline", "title": "Due dates", "description": "due_date", "recommended": True},
        {
            "block": "DataTable",
            "title": "All loans",
            "description": "every field",
            "recommended": False,
        },
    ],
    "primary": 1,
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


@pytest.mark.parametrize(
    "args",
    [
        {"questions": []},
        {"questions": [{"question": "x", "options": ["only one"], "recommended": 0}]},
        {"questions": [{"question": "q", "options": ["a", "b"], "recommended": 0}] * 4},
    ],
)
async def test_ask_user_validates(args):
    ctx, _ = _ctx()
    with pytest.raises(ToolError):
        await TOOLS["ask_user"].handler(ctx, args)


async def test_propose_views_stores_options_and_primary():
    ctx, p = _ctx()
    await TOOLS["propose_views"].handler(ctx, VIEWS)
    assert [o["id"] for o in p.setup["layout_options"]] == ["v1", "v2", "v3"]
    assert p.setup["layout_primary"] == "v2" and p.setup["layout_state"] == "choosing"
    with pytest.raises(ToolError, match="block"):
        await TOOLS["propose_views"].handler(
            ctx, {"options": [{"block": "Pie", "title": "x"}] * 2, "primary": 0}
        )


async def test_choose_layout_uses_the_users_choice_or_the_recommended_ones():
    ctx, p = _ctx(wait=5)
    await TOOLS["propose_views"].handler(ctx, VIEWS)
    p.setup["layout"] = {"views": ["v3", "v1"], "primary": "v3"}
    await flows.choose_layout(ctx)
    layout = ctx.state.config["layout"]
    assert [v["id"] for v in layout["views"]] == ["v1", "v3"] and layout["primary"] == "v3"
    assert p.setup["layout_state"] == "chosen"
    text = app_input("p", "g", {}, 10_000, name="Loans", layout=layout)
    assert "<name>Loans</name>" in text
    assert text.index("All loans (DataTable)") < text.index("Board by status (Board)")

    ctx2, p2 = _ctx()
    await TOOLS["propose_views"].handler(ctx2, VIEWS)
    await flows.choose_layout(ctx2)
    assert [v["id"] for v in ctx2.state.config["layout"]["views"]] == ["v1", "v2"]
    assert ctx2.state.config["layout"]["primary"] == "v2"


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


async def test_setup_api_look_answers_and_layout(client, session):
    ws = (await client.post(URL, json=BODY)).json()
    detail = (await client.get(f"{URL}/{ws['id']}")).json()
    setup = detail["active_run"]["setup"]
    assert setup["palette"] is None and setup["questions_state"] == "deciding"
    assert setup["layout_state"] == "waiting"

    resp = await client.post(f"{URL}/{ws['id']}/setup", json={"palette": "teal"})
    assert resp.status_code == 200 and resp.json()["setup"]["palette"] == "teal"
    assert (await session.get(Workspace, ws["id"])).palette == "teal"

    # Nothing to answer yet.
    early = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q1": "Yes"}})
    assert early.status_code == 409

    run = await _build_run(session, ws["id"])
    run.input = {
        **run.input,
        "look": {"palette": "teal"},
        "questions": [{"id": "q1", "question": "E-books?", "options": ["Yes", "No"],
                       "recommended": 1}],
        "questions_state": "asking",
        "layout_options": [{"id": "v1", "block": "Board", "title": "Board"},
                           {"id": "v2", "block": "DataTable", "title": "Table"}],
        "layout_state": "choosing",
    }  # fmt: skip
    await session.flush()

    bad = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q9": "Yes"}})
    assert bad.status_code == 422
    ok = await client.post(f"{URL}/{ws['id']}/setup", json={"answers": {"q1": "Yes"}})
    assert ok.status_code == 200 and ok.json()["setup"]["answered"] is True

    wrong = await client.post(
        f"{URL}/{ws['id']}/setup", json={"layout": {"views": ["v1"], "primary": "v2"}}
    )
    assert wrong.status_code == 422
    chosen = await client.post(
        f"{URL}/{ws['id']}/setup", json={"layout": {"views": ["v2", "v1"], "primary": "v2"}}
    )
    assert chosen.status_code == 200 and chosen.json()["setup"]["layout_chosen"] is True
    await session.refresh(run)
    assert run.input["layout"] == {"views": ["v2", "v1"], "primary": "v2"}
    assert run.input["answers"] == {"q1": "Yes"} and run.input["look"] == {"palette": "teal"}


async def test_setup_api_isolation_and_finished_builds(client, other_client, session):
    ws = (await client.post(URL, json=BODY)).json()
    other = await other_client.post(f"{URL}/{ws['id']}/setup", json={"palette": "rose"})
    assert other.status_code == 404
    await session.execute(Run.__table__.update().values(status=RunStatus.DONE.value))
    done = await client.post(f"{URL}/{ws['id']}/setup", json={"palette": "rose"})
    assert done.status_code == 409
    assert (
        await client.post(f"{URL}/{ws['id']}/setup", json={"palette": "red"})
    ).status_code == 422
