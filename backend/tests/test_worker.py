"""Worker: claiming (one run per workspace) and executing runs against the DB."""

from sqlalchemy import func, select

from app.models import Change, ProcessedMessage, Run, RunKind, RunStatus, Workspace
from app.services import runs
from app.services.workspaces import create_workspace
from app.worker import execute_run
from tests.helpers import GOOD_APP, SMALL_MAILBOX, ScriptedLLM, dt
from tests.test_flows import DESIGN_TURNS, build_llm


async def test_claim_one_run_per_workspace(session, dev_user):
    ws = await create_workspace(session, dev_user.id, "orders")
    ws2 = await create_workspace(session, dev_user.id, "other")
    # A second run queued for ws behind the build (as if the build finished enqueueing).
    session.add(Run(workspace_id=ws.id, kind=RunKind.SYNC, status=RunStatus.QUEUED))
    await session.flush()
    first = await runs.claim_next(session)
    second = await runs.claim_next(session)
    third = await runs.claim_next(session)
    assert {first.workspace_id, second.workspace_id} == {ws.id, ws2.id}
    assert third is None  # ws's sync waits for its running build


async def test_execute_build_then_sync(session, session_factory, dev_user):
    from app.mail.fake import FakeMailbox

    box = FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-16T00:00:00Z"))
    ws = await create_workspace(session, dev_user.id, "track orders")
    run = await runs.claim_next(session)
    llm = build_llm()
    await execute_run(
        run.id,
        llm=llm,
        mailbox_factory=lambda _uid: box,
        session_factory=session_factory,
        now=dt("2026-10-16T00:00:00Z"),
    )
    await session.refresh(run)
    await session.refresh(ws)
    assert run.status == RunStatus.DONE, run.error
    assert ws.status == "ready" and ws.app_html == GOOD_APP and ws.data["order"]
    assert ws.data_version >= 1 and ws.app_version == 1
    assert run.input_tokens > 0 and float(run.cost_usd) > 0
    assert any(e["label"].startswith("Saved") for e in run.events)
    n_changes = await session.scalar(select(func.count()).select_from(Change))
    assert n_changes == len(ws.data["order"])
    assert await session.scalar(select(func.count()).select_from(ProcessedMessage)) == 7

    # Sync with nothing new: no LLM call, run kept as "No new emails".
    sync = await runs.enqueue(session, ws.id, RunKind.SYNC)
    await runs.claim_next(session)
    empty = ScriptedLLM([])
    await execute_run(
        sync.id,
        llm=empty,
        mailbox_factory=lambda _uid: box,
        session_factory=session_factory,
        now=dt("2026-10-16T00:10:00Z"),
    )
    await session.refresh(sync)
    assert sync.summary == "No new emails" and empty.calls == []


async def test_cannot_build_fails_workspace(session, session_factory, dev_user):
    from app.mail.fake import FakeMailbox

    box = FakeMailbox.from_file(SMALL_MAILBOX)
    ws = await create_workspace(session, dev_user.id, "my heart rate")
    run = await runs.claim_next(session)
    llm = ScriptedLLM([[("finish", {"summary": "CANNOT_BUILD: heart rate is not in email."})]])
    await execute_run(
        run.id, llm=llm, mailbox_factory=lambda _u: box, session_factory=session_factory
    )
    await session.refresh(ws)
    await session.refresh(run)
    assert run.status == RunStatus.FAILED and ws.status == "failed"
    assert ws.last_error == "heart rate is not in email."
    w = await session.get(Workspace, ws.id)
    assert w is not None


NAMED_DESIGN = [
    [("set_name", {"name": "Track Every Online Order"})],  # too long: retried
    [("set_name", {"name": '"Online Orders."'})],
    *DESIGN_TURNS,
]


async def test_build_names_the_workspace(session, session_factory, dev_user):
    ws = await create_workspace(session, dev_user.id, "show me all my online orders please")
    assert ws.name == "show me all my online orders please"  # until the build names it
    from app.mail.fake import FakeMailbox

    box = FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-16T00:00:00Z"))
    run = await runs.claim_next(session)
    await execute_run(
        run.id,
        llm=build_llm(design=NAMED_DESIGN),
        mailbox_factory=lambda _uid: box,
        session_factory=session_factory,
        now=dt("2026-10-16T00:00:00Z"),
    )
    await session.refresh(ws)
    await session.refresh(run)
    assert run.status == RunStatus.DONE, run.error
    assert ws.name == "Online Orders"  # >3 words rejected; quotes and dot stripped


async def test_build_keeps_a_name_the_user_chose(session, session_factory, dev_user):
    from app.mail.fake import FakeMailbox

    ws = await create_workspace(session, dev_user.id, "track orders")
    ws.name = "My Shopping"  # renamed before the build got to it
    await session.flush()
    box = FakeMailbox.from_file(SMALL_MAILBOX, now=dt("2026-10-16T00:00:00Z"))
    run = await runs.claim_next(session)
    await execute_run(
        run.id,
        llm=build_llm(design=NAMED_DESIGN),
        mailbox_factory=lambda _uid: box,
        session_factory=session_factory,
        now=dt("2026-10-16T00:00:00Z"),
    )
    await session.refresh(ws)
    await session.refresh(run)
    assert run.status == RunStatus.DONE, run.error
    assert ws.name == "My Shopping"


async def test_no_scheduled_sync_without_gmail(session, dev_user):
    from app.auth.google import unlink_gmail
    from app.models.workspace import WorkspaceStatus

    ws = Workspace(user_id=dev_user.id, name="orders", prompt="orders")
    ws.status = WorkspaceStatus.READY
    session.add(ws)
    await session.flush()
    assert ws.id in await runs.workspaces_due_for_sync(session, 10)
    await unlink_gmail(session, dev_user)
    assert ws.id not in await runs.workspaces_due_for_sync(session, 10)
