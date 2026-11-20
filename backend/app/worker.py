"""Worker process: executes queued runs and schedules syncs (`make worker`).

- Claims queued runs from Postgres (`FOR UPDATE SKIP LOCKED`), at most one run per
  workspace at a time, up to WORKER_CONCURRENCY runs in parallel.
- Every SYNC_INTERVAL_MIN, enqueues a sync for each `ready` workspace with no active run
  (skipping users who must reconnect Gmail).
- Logs ids, counts and costs only.
"""

import asyncio
import logging
import signal
import uuid
from datetime import UTC, datetime

from sqlalchemy import update

from app.agent import flows
from app.agent.context import BudgetExceeded, RunContext, WorkspaceState
from app.agent.llm import ChatModel, LLMError, OpenAICompatibleLLM
from app.agent.loop import PhaseFailed
from app.auth.google import UserTokenProvider
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal
from app.mail.base import Mailbox, MailboxError, ReconnectRequired
from app.mail.gmail import GmailMailbox
from app.models.run import Run, RunKind, RunStatus
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceStatus
from app.services import runs

logger = logging.getLogger("app.worker")


def gmail_for(user_id: uuid.UUID) -> Mailbox:
    if settings.uses_fake_mailbox:
        from app.mail.fake import FakeMailbox

        return FakeMailbox.from_file(settings.DEV_FAKE_MAILBOX)
    return GmailMailbox(UserTokenProvider(SessionLocal, user_id))


async def execute_run(
    run_id: uuid.UUID,
    *,
    llm: ChatModel | None = None,
    mailbox_factory=gmail_for,
    session_factory=SessionLocal,
    now: datetime | None = None,
) -> None:
    """Execute one claimed (running) run end to end and record its outcome."""
    async with session_factory() as s:
        run = await s.get(Run, run_id)
        assert run is not None
        ws = await s.get(Workspace, run.workspace_id)
        assert ws is not None
        user = await s.get(User, ws.user_id)
        assert user is not None
        kind, payload, user_id, ws_id = run.kind, dict(run.input), user.id, ws.id
        needs_reconnect = user.needs_reconnect
        if kind == RunKind.BUILD:
            ws.status = WorkspaceStatus.BUILDING
            ws.last_error = None
            await s.commit()
        state = WorkspaceState(
            prompt=ws.prompt,
            name=ws.name,
            data=dict(ws.data or {}),
            guide=ws.guide,
            config=dict(ws.config or {}),
            app_html=ws.app_html,
            data_version=ws.data_version,
            app_version=ws.app_version,
            last_synced_at=ws.last_synced_at,
        )
        recent = await runs.recent_summaries(s, ws_id) if kind == RunKind.EDIT else []

    persister = runs.DbPersister(session_factory, ws_id, run_id, user_id)
    mailbox = mailbox_factory(user_id)
    ctx = RunContext(
        state=state,
        mailbox=mailbox,
        persister=persister,
        run_id=str(run_id),
        now=now or datetime.now(UTC),
        lookback_days=settings.LOOKBACK_DAYS,
        max_build_threads=settings.BUILD_MAX_THREADS,
        inline_max_chars=settings.DATA_INLINE_MAX_CHARS,
    )
    cfg = flows.FlowConfig.from_settings(llm or OpenAICompatibleLLM())

    status, summary, error, ws_status = RunStatus.DONE, None, None, None
    try:
        if needs_reconnect:
            raise ReconnectRequired("reconnect required")
        if kind == RunKind.BUILD:
            summary = await flows.build(ctx, cfg)
            ws_status = WorkspaceStatus.READY
        elif kind == RunKind.SYNC:
            summary = await flows.sync(ctx, cfg)
        else:
            summary = await flows.edit(ctx, cfg, str(payload.get("text", "")), recent)
    except flows.CannotBuild as e:
        status, error, ws_status = RunStatus.FAILED, str(e), WorkspaceStatus.FAILED
    except ReconnectRequired:
        status, error = (
            RunStatus.FAILED,
            "reconnect_required: Gmail access expired. Reconnect Gmail.",
        )
        async with session_factory() as s:
            await s.execute(update(User).where(User.id == user_id).values(needs_reconnect=True))
            await s.commit()
    except BudgetExceeded as e:
        status, error = RunStatus.FAILED, f"budget_exceeded: {e}"
    except LLMError as e:
        status, error = RunStatus.FAILED, f"llm_error: {e}"
    except PhaseFailed:
        status, error = (
            RunStatus.FAILED,
            "agent_stuck: The agent could not finish this step. Try again, or rephrase.",
        )
    except MailboxError as e:
        status, error = RunStatus.FAILED, f"mail_error: Gmail could not be read ({e})."
    except Exception as e:  # noqa: BLE001 - the worker must survive any run
        logger.exception("run %s crashed", run_id)
        status, error = RunStatus.FAILED, f"internal_error: {type(e).__name__}"
    finally:
        aclose = getattr(mailbox, "aclose", None)
        if aclose:
            await aclose()

    if status == RunStatus.FAILED and kind == RunKind.BUILD:
        ws_status = WorkspaceStatus.FAILED

    async with session_factory() as s:
        run = await s.get(Run, run_id)
        assert run is not None
        run.status = status
        run.summary = summary
        run.error = error
        run.finished_at = datetime.now(UTC)
        values: dict = {}
        if ws_status is not None:
            values["status"] = ws_status
        if kind == RunKind.BUILD:
            values["last_error"] = error
        if values:
            await s.execute(update(Workspace).where(Workspace.id == ws_id).values(**values))
        if kind == RunKind.SYNC and summary == runs.NO_NEW_EMAILS:
            await runs.prune_empty_syncs(s, ws_id, keep=run_id)
        await s.commit()
    logger.info(
        "run %s kind=%s status=%s cost=%.4f", run_id, kind.value, status.value, persister.cost
    )


class Worker:
    def __init__(self) -> None:
        self.tasks: set[asyncio.Task] = set()
        self.stopping = asyncio.Event()
        self.last_schedule = 0.0

    async def schedule_syncs(self) -> None:
        async with SessionLocal() as s:
            due = await runs.workspaces_due_for_sync(s, settings.SYNC_INTERVAL_MIN)
            for ws_id in due:
                await runs.enqueue(s, ws_id, RunKind.SYNC, conflict_if_active=False)
            await s.commit()
        if due:
            logger.info("scheduled %s syncs", len(due))

    async def claim(self) -> uuid.UUID | None:
        async with SessionLocal() as s:
            run = await runs.claim_next(s)
            await s.commit()
            return run.id if run else None

    async def loop(self) -> None:
        async with SessionLocal() as s:
            n = await runs.fail_stale_running(s)
            await s.commit()
        if n:
            logger.info("marked %s interrupted runs as failed", n)
        logger.info(
            "worker started: concurrency=%s sync_interval=%smin",
            settings.WORKER_CONCURRENCY,
            settings.SYNC_INTERVAL_MIN,
        )
        loop = asyncio.get_running_loop()
        while not self.stopping.is_set():
            try:
                if loop.time() - self.last_schedule >= 60:
                    self.last_schedule = loop.time()
                    await self.schedule_syncs()
                while len(self.tasks) < settings.WORKER_CONCURRENCY:
                    run_id = await self.claim()
                    if run_id is None:
                        break
                    logger.info("claimed run %s", run_id)
                    task = asyncio.create_task(execute_run(run_id))
                    self.tasks.add(task)
                    task.add_done_callback(self.tasks.discard)
            except Exception:  # noqa: BLE001
                logger.exception("worker tick failed")
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=2)
            except TimeoutError:
                pass
        if self.tasks:
            logger.info("waiting for %s running runs", len(self.tasks))
            await asyncio.gather(*self.tasks, return_exceptions=True)


async def main() -> None:
    setup_logging(settings.ENV, settings.LOG_LEVEL)
    worker = Worker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stopping.set)
    await worker.loop()


if __name__ == "__main__":
    asyncio.run(main())
