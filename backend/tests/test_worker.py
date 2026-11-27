"""Worker: claiming (one run per workspace) and executing runs against the DB."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.agent.context import BudgetExceeded
from app.models import Change, LLMCall, ProcessedMessage, Run, RunKind, RunStatus, Workspace
from app.services import runs
from app.services.workspaces import create_workspace, delete_workspace
from app.worker import execute_run
from tests.helpers import SMALL_MAILBOX, ScriptedLLM, dt
from tests.test_flows import DESIGN_TURNS, GOOD_STUDIO_APP, build_llm


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
    assert ws.status == "ready" and ws.app_html == GOOD_STUDIO_APP and ws.data["order"]
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


def _llm_call(user_id, cost: float, phase: str = "design", **ids) -> LLMCall:
    zero = Decimal(0)
    return LLMCall(
        user_id=user_id,
        phase=phase,
        model="m",
        provider="p",
        input_price=zero,
        cached_input_price=zero,
        output_price=zero,
        cost_usd=Decimal(str(cost)),
        status="ok",
        **ids,
    )


async def test_daily_budget_survives_deleting_a_workspace(session, session_factory, dev_user):
    """Runs are deleted with their workspace; today's spend must not be."""
    ws1 = await create_workspace(session, dev_user.id, "first")
    run1 = await runs.active_run(session, ws1.id)
    run1.cost_usd = Decimal("14.5")
    session.add(_llm_call(dev_user.id, 14.5, run_id=run1.id, workspace_id=ws1.id))
    await session.flush()
    await delete_workspace(session, dev_user.id, ws1.id)

    ws2 = await create_workspace(session, dev_user.id, "second")
    run2 = await runs.active_run(session, ws2.id)
    session.add(_llm_call(dev_user.id, 1.0, run_id=run2.id, workspace_id=ws2.id))
    await session.flush()
    persister = runs.DbPersister(session_factory, ws2.id, run2.id, dev_user.id)
    with pytest.raises(BudgetExceeded, match="Today"):
        await persister.add_usage(10, 10, 1.0)


async def test_daily_budget_ignores_demo_seeds(session, dev_user):
    session.add(_llm_call(dev_user.id, 20.0, phase="seed"))
    session.add(_llm_call(dev_user.id, 1.25))
    await session.flush()
    assert await runs.spent_today(session, dev_user.id) == pytest.approx(1.25)
