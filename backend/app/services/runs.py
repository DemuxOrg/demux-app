"""Runs: enqueue, claim (worker), history, activity feed, and the DB persister used by
agent flows.

User-facing functions take `user_id` and scope through `workspaces.user_id`. Worker
functions operate on ids the worker claimed itself.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, delete, exists, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.context import BudgetExceeded, WorkspaceState
from app.core.config import settings
from app.core.errors import ConflictError
from app.models.run import Change, Run, RunKind, RunStatus
from app.models.workspace import Workspace
from app.services import store
from app.services.store import ChangeRow

ACTIVE = (RunStatus.QUEUED, RunStatus.RUNNING)
NO_NEW_EMAILS = "No new emails"


async def active_run(session: AsyncSession, workspace_id: uuid.UUID) -> Run | None:
    return await session.scalar(
        select(Run)
        .where(Run.workspace_id == workspace_id, Run.status.in_(ACTIVE))
        .order_by(Run.created_at)
        .limit(1)
    )


async def enqueue(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    kind: RunKind,
    payload: dict[str, Any] | None = None,
    *,
    conflict_if_active: bool = True,
) -> Run:
    # Serialize enqueues per workspace so two requests can't both pass the active check.
    await session.execute(
        select(Workspace.id).where(Workspace.id == workspace_id).with_for_update()
    )
    current = await active_run(session, workspace_id)
    if current is not None:
        if conflict_if_active:
            raise ConflictError("A run is already in progress for this workspace.")
        return current
    run = Run(workspace_id=workspace_id, kind=kind, status=RunStatus.QUEUED, input=payload or {})
    session.add(run)
    await session.flush()
    return run


async def list_runs(session: AsyncSession, workspace_id: uuid.UUID, limit: int) -> list[Run]:
    return list(
        await session.scalars(
            select(Run)
            .where(Run.workspace_id == workspace_id)
            .order_by(Run.created_at.desc())
            .limit(limit)
        )
    )


async def recent_summaries(session: AsyncSession, workspace_id: uuid.UUID, n: int = 5) -> list[str]:
    rows = await session.execute(
        select(Run.kind, Run.summary, Run.input)
        .where(
            Run.workspace_id == workspace_id,
            Run.status == RunStatus.DONE,
            Run.summary.is_not(None),
            Run.summary != NO_NEW_EMAILS,
        )
        .order_by(Run.created_at.desc())
        .limit(n)
    )
    out = []
    for kind, summary, payload in rows:
        prefix = f"{kind.value}"
        if kind == RunKind.EDIT and payload.get("text"):
            prefix += f' (user asked: "{payload["text"][:200]}")'
        out.append(f"{prefix}: {summary}")
    return list(reversed(out))


async def list_changes(
    session: AsyncSession, workspace_id: uuid.UUID, limit: int, before: datetime | None
) -> list[Change]:
    q = select(Change).where(Change.workspace_id == workspace_id)
    if before is not None:
        q = q.where(Change.created_at < before)
    return list(await session.scalars(q.order_by(Change.created_at.desc()).limit(limit)))


async def spent_today(session: AsyncSession, user_id: uuid.UUID) -> float:
    midnight = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    total = await session.scalar(
        select(func.coalesce(func.sum(Run.cost_usd), 0))
        .join(Workspace, Workspace.id == Run.workspace_id)
        .where(Workspace.user_id == user_id, Run.created_at >= midnight)
    )
    return float(total or 0)


# ------------------------------------------------------------------ worker side


async def claim_next(session: AsyncSession) -> Run | None:
    """Claim the oldest queued run whose workspace has no running run."""
    other = Run.__table__.alias("other")
    run = await session.scalar(
        select(Run)
        .where(
            Run.status == RunStatus.QUEUED,
            ~exists().where(
                and_(other.c.workspace_id == Run.workspace_id, other.c.status == "running")
            ),
        )
        .order_by(Run.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if run is None:
        return None
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await session.flush()
    return run


async def fail_stale_running(session: AsyncSession) -> int:
    """At worker start: runs left `running` by a crashed worker are failed."""
    result = await session.execute(
        update(Run)
        .where(Run.status == RunStatus.RUNNING)
        .values(
            status=RunStatus.FAILED, error="Interrupted (worker restarted).", finished_at=func.now()
        )
    )
    return result.rowcount or 0  # type: ignore[attr-defined]


async def workspaces_due_for_sync(session: AsyncSession, interval_min: int) -> list[uuid.UUID]:
    from app.models.user import User
    from app.models.workspace import WorkspaceStatus

    cutoff = datetime.now(UTC) - timedelta(minutes=interval_min)
    rows = await session.scalars(
        select(Workspace.id)
        .join(User, User.id == Workspace.user_id)
        .where(
            Workspace.status == WorkspaceStatus.READY,
            User.needs_reconnect.is_(False),
            (Workspace.last_synced_at.is_(None)) | (Workspace.last_synced_at < cutoff),
            ~exists().where(Run.workspace_id == Workspace.id, Run.status.in_(ACTIVE)),
        )
    )
    return list(rows)


async def prune_empty_syncs(
    session: AsyncSession, workspace_id: uuid.UUID, keep: uuid.UUID
) -> None:
    await session.execute(
        delete(Run).where(
            Run.workspace_id == workspace_id,
            Run.kind == RunKind.SYNC,
            Run.status == RunStatus.DONE,
            Run.summary == NO_NEW_EMAILS,
            Run.id != keep,
        )
    )


class DbPersister:
    """Persister for real runs: every write is its own short transaction."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        self.sf = session_factory
        self.workspace_id = workspace_id
        self.run_id = run_id
        self.user_id = user_id
        self.cost = 0.0

    async def _ws_update(self, **values: Any) -> None:
        async with self.sf() as s:
            await s.execute(
                update(Workspace).where(Workspace.id == self.workspace_id).values(**values)
            )
            await s.commit()

    async def save_data(self, state: WorkspaceState, changes: list[ChangeRow]) -> None:
        async with self.sf() as s:
            state.data_version = await store.persist_data(
                s, self.workspace_id, self.run_id, state.data, changes
            )
            await s.commit()

    async def save_guide(self, state: WorkspaceState) -> None:
        await self._ws_update(guide=state.guide)

    async def save_config(self, state: WorkspaceState) -> None:
        await self._ws_update(config=state.config)

    async def save_app(self, state: WorkspaceState) -> None:
        async with self.sf() as s:
            version = await s.scalar(
                update(Workspace)
                .where(Workspace.id == self.workspace_id)
                .values(app_html=state.app_html, app_version=Workspace.app_version + 1)
                .returning(Workspace.app_version)
            )
            await s.commit()
        state.app_version = int(version or 0)

    async def save_synced(self, state: WorkspaceState) -> None:
        await self._ws_update(last_synced_at=state.last_synced_at)

    async def add_event(self, event: dict[str, Any]) -> None:
        import json

        async with self.sf() as s:
            await s.execute(
                text("UPDATE runs SET events = events || CAST(:ev AS jsonb) WHERE id = :id"),
                {"ev": json.dumps([event]), "id": self.run_id},
            )
            await s.commit()

    async def add_usage(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        self.cost += cost
        async with self.sf() as s:
            await s.execute(
                update(Run)
                .where(Run.id == self.run_id)
                .values(
                    input_tokens=Run.input_tokens + input_tokens,
                    output_tokens=Run.output_tokens + output_tokens,
                    cost_usd=Run.cost_usd + Decimal(str(round(cost, 6))),
                )
            )
            await s.commit()
            today = await spent_today(s, self.user_id)
        if self.cost > settings.MAX_USD_PER_RUN:
            raise BudgetExceeded(
                f"This run reached its ${settings.MAX_USD_PER_RUN:.2f} spending limit."
            )
        if today > settings.MAX_USD_PER_DAY:
            raise BudgetExceeded(
                f"Today's ${settings.MAX_USD_PER_DAY:.2f} spending limit was reached."
            )

    async def processed_ids(self) -> set[str]:
        async with self.sf() as s:
            return await store.processed_message_ids(s, self.workspace_id)

    async def processed_thread_ids(self) -> list[str]:
        async with self.sf() as s:
            return await store.processed_thread_ids(s, self.workspace_id)

    async def mark_processed(self, pairs: list[tuple[str, str]]) -> None:
        async with self.sf() as s:
            await store.mark_processed(s, self.workspace_id, self.run_id, pairs)
            await s.commit()

    async def snapshot(self) -> None:
        async with self.sf() as s:
            await store.take_snapshot(s, self.workspace_id, self.run_id)
            await s.commit()

    async def restore_snapshot(self) -> None:
        async with self.sf() as s:
            await store.restore_run_snapshot(s, self.workspace_id, self.run_id)
            await s.commit()
