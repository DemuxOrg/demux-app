"""Usage and cost statistics for /admin.

Privacy (Google's Gmail user-data policy): these queries read ids, counts, tokens,
costs, statuses, dates, and the text users typed (workspace prompts, edit-chat
messages). They never select email content, subjects, senders, record values
(`workspaces.data`), the guide, app HTML, or run summaries (written from emails).

Days are UTC. A range of N days ends today and includes it. Costs come from
`llm_calls` (they survive deleted workspaces); activity counts come from `runs`.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, cast, distinct, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.models.auth import AuthSession
from app.models.run import ProcessedMessage, Run, RunKind, RunStatus
from app.models.usage import LLMCall, MailboxDailyStat
from app.models.user import User
from app.models.workspace import Workspace

RANGES = (7, 30, 90)
# Staff spending (demo inbox, evals): in the totals, never in a user's cost.
STAFF_PHASES = ("seed", "eval")
RUNS_PER_WORKSPACE = 50
# Prefixes the worker puts on run errors (app/worker.py); anything else is shown as a code.
ERROR_CODES = (
    "reconnect_required",
    "budget_exceeded",
    "llm_error",
    "agent_stuck",
    "mail_error",
    "internal_error",
)


def _today() -> date:
    return datetime.now(UTC).date()


def _days(n: int, end: date | None = None) -> list[date]:
    end = end or _today()
    return [end - timedelta(days=n - 1 - i) for i in range(n)]


def _start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)


def _day(col: Any) -> Any:
    """A timestamptz column as its UTC calendar day."""
    return cast(func.timezone("UTC", col), Date)


def _f(value: Decimal | float | None) -> float:
    return round(float(value or 0), 6)


def error_code(run: Run) -> str | None:
    if run.status != RunStatus.FAILED:
        return None
    text = run.error or ""
    prefix = text.split(":", 1)[0]
    if prefix in ERROR_CODES:
        return prefix
    if text.startswith("Interrupted"):
        return "interrupted"
    # The design phase's "can't build" reason is free text drawn from the inbox: not shown.
    return "cannot_build" if run.kind == RunKind.BUILD else "error"


def duration_s(run: Run) -> float | None:
    if run.started_at and run.finished_at:
        return round((run.finished_at - run.started_at).total_seconds(), 1)
    return None


# ------------------------------------------------------------------ overview


@dataclass
class Overview:
    days: int
    start: date
    end: date
    active_users: int
    total_users: int
    workspaces: int
    new_workspaces: int
    builds: int
    syncs: int
    edits: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    failed_runs: int
    finished_runs: int
    cost_by_phase: list[tuple[date, str, float]]
    cost_by_model: list[tuple[date, str, float]]
    tokens: list[tuple[date, int, int]]
    cost_per_user: list[tuple[date, int, float, float]]  # day, users, p50, p95
    failures: list[tuple[date, int, int]]  # day, finished, failed


async def overview(session: AsyncSession, days: int) -> Overview:
    span = _days(days)
    start = _start(span[0])
    in_range = LLMCall.created_at >= start
    run_range = Run.created_at >= start

    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(LLMCall.input_tokens), 0),
                func.coalesce(func.sum(LLMCall.output_tokens), 0),
                func.coalesce(func.sum(LLMCall.cost_usd), 0),
            ).where(in_range)
        )
    ).one()
    kinds = dict(
        (
            await session.execute(
                select(Run.kind, func.count()).where(run_range).group_by(Run.kind)
            )
        ).all()
    )
    finished, failed = (
        await session.execute(
            select(
                func.count().filter(Run.status.in_((RunStatus.DONE, RunStatus.FAILED))),
                func.count().filter(Run.status == RunStatus.FAILED),
            ).where(run_range)
        )
    ).one()
    active = await session.scalar(
        select(func.count(distinct(Workspace.user_id)))
        .select_from(Run)
        .join(Workspace, Workspace.id == Run.workspace_id)
        .where(run_range)
    )
    ws_total, ws_new = (
        await session.execute(
            select(func.count(), func.count().filter(Workspace.created_at >= start))
        )
    ).one()
    total_users = await session.scalar(select(func.count()).select_from(User))

    day = _day(LLMCall.created_at)
    by_phase = [
        (d, p, _f(c))
        for d, p, c in await session.execute(
            select(day, LLMCall.phase, func.sum(LLMCall.cost_usd))
            .where(in_range)
            .group_by(day, LLMCall.phase)
            .order_by(day)
        )
    ]
    by_model = [
        (d, m, _f(c))
        for d, m, c in await session.execute(
            select(day, LLMCall.model, func.sum(LLMCall.cost_usd))
            .where(in_range)
            .group_by(day, LLMCall.model)
            .order_by(day)
        )
    ]
    tok = {
        d: (int(i or 0), int(o or 0))
        for d, i, o in await session.execute(
            select(day, func.sum(LLMCall.input_tokens), func.sum(LLMCall.output_tokens))
            .where(in_range)
            .group_by(day)
        )
    }

    per_user = (
        select(day.label("d"), LLMCall.user_id, func.sum(LLMCall.cost_usd).label("c"))
        .where(in_range, LLMCall.user_id.is_not(None), LLMCall.phase.not_in(STAFF_PHASES))
        .group_by(day, LLMCall.user_id)
        .subquery()
    )
    pct = {
        d: (int(n), _f(p50), _f(p95))
        for d, n, p50, p95 in await session.execute(
            select(
                per_user.c.d,
                func.count(),
                func.percentile_cont(0.5).within_group(per_user.c.c),
                func.percentile_cont(0.95).within_group(per_user.c.c),
            ).group_by(per_user.c.d)
        )
    }

    rday = _day(Run.created_at)
    fails = {
        d: (int(f or 0), int(x or 0))
        for d, f, x in await session.execute(
            select(
                rday,
                func.count().filter(Run.status.in_((RunStatus.DONE, RunStatus.FAILED))),
                func.count().filter(Run.status == RunStatus.FAILED),
            )
            .where(run_range)
            .group_by(rday)
        )
    }

    return Overview(
        days=days,
        start=span[0],
        end=span[-1],
        active_users=int(active or 0),
        total_users=int(total_users or 0),
        workspaces=int(ws_total or 0),
        new_workspaces=int(ws_new or 0),
        builds=int(kinds.get(RunKind.BUILD, 0)),
        syncs=int(kinds.get(RunKind.SYNC, 0)),
        edits=int(kinds.get(RunKind.EDIT, 0)),
        input_tokens=int(totals[0]),
        output_tokens=int(totals[1]),
        cost_usd=_f(totals[2]),
        failed_runs=int(failed or 0),
        finished_runs=int(finished or 0),
        cost_by_phase=by_phase,
        cost_by_model=by_model,
        tokens=[(d, *tok.get(d, (0, 0))) for d in span],
        cost_per_user=[(d, *pct.get(d, (0, 0.0, 0.0))) for d in span],
        failures=[(d, *fails.get(d, (0, 0))) for d in span],
    )


# ------------------------------------------------------------------ users


@dataclass
class UserRow:
    id: uuid.UUID
    email: str
    name: str
    created_at: datetime
    last_active_at: datetime | None
    workspaces: int
    emails_processed: int
    emails_received_per_day: float | None
    cost_7d: float
    cost_30d: float
    cost_total: float
    gmail_connected: bool
    needs_reconnect: bool


async def _last_active(session: AsyncSession, user_ids: list[uuid.UUID] | None = None) -> dict:
    q_sess = select(AuthSession.user_id, func.max(AuthSession.updated_at)).group_by(
        AuthSession.user_id
    )
    q_runs = (
        select(Workspace.user_id, func.max(Run.created_at))
        .join(Run, Run.workspace_id == Workspace.id)
        .group_by(Workspace.user_id)
    )
    if user_ids is not None:
        q_sess = q_sess.where(AuthSession.user_id.in_(user_ids))
        q_runs = q_runs.where(Workspace.user_id.in_(user_ids))
    out: dict[uuid.UUID, datetime] = {}
    for uid, ts in [*(await session.execute(q_sess)), *(await session.execute(q_runs))]:
        if ts is not None and (uid not in out or ts > out[uid]):
            out[uid] = ts
    return out


async def _received_per_day(
    session: AsyncSession, user_ids: list[uuid.UUID] | None = None
) -> dict[uuid.UUID, float]:
    """Average messages received per day over the last 7 finished days (days counted)."""
    since = _today() - timedelta(days=7)
    q = (
        select(MailboxDailyStat.user_id, func.avg(MailboxDailyStat.messages_received))
        .where(MailboxDailyStat.date >= since)
        .group_by(MailboxDailyStat.user_id)
    )
    if user_ids is not None:
        q = q.where(MailboxDailyStat.user_id.in_(user_ids))
    return {uid: round(float(avg), 1) for uid, avg in await session.execute(q)}


async def _costs(
    session: AsyncSession, key: Any, where: list[Any]
) -> dict[Any, tuple[float, float, float]]:
    now = datetime.now(UTC)
    d7, d30 = _start(_days(7)[0]), _start(_days(30)[0])
    rows = await session.execute(
        select(
            key,
            func.coalesce(func.sum(LLMCall.cost_usd).filter(LLMCall.created_at >= d7), 0),
            func.coalesce(func.sum(LLMCall.cost_usd).filter(LLMCall.created_at >= d30), 0),
            func.coalesce(func.sum(LLMCall.cost_usd), 0),
        )
        .where(LLMCall.created_at <= now, *where)
        .group_by(key)
    )
    return {k: (_f(a), _f(b), _f(c)) for k, a, b, c in rows}


async def users_table(session: AsyncSession) -> list[UserRow]:
    users = list(await session.scalars(select(User)))
    ws_counts = dict(
        (
            await session.execute(
                select(Workspace.user_id, func.count()).group_by(Workspace.user_id)
            )
        ).all()
    )
    processed = dict(
        (
            await session.execute(
                select(Workspace.user_id, func.count())
                .join(ProcessedMessage, ProcessedMessage.workspace_id == Workspace.id)
                .group_by(Workspace.user_id)
            )
        ).all()
    )
    received = await _received_per_day(session)
    costs = await _costs(session, LLMCall.user_id, [LLMCall.phase.not_in(STAFF_PHASES)])
    active = await _last_active(session)
    rows = [
        UserRow(
            id=u.id,
            email=u.email,
            name=" ".join(p for p in (u.first_name, u.last_name) if p) or u.name,
            created_at=u.created_at,
            last_active_at=active.get(u.id),
            workspaces=int(ws_counts.get(u.id, 0)),
            emails_processed=int(processed.get(u.id, 0)),
            emails_received_per_day=received.get(u.id),
            cost_7d=costs.get(u.id, (0.0, 0.0, 0.0))[0],
            cost_30d=costs.get(u.id, (0.0, 0.0, 0.0))[1],
            cost_total=costs.get(u.id, (0.0, 0.0, 0.0))[2],
            gmail_connected=bool(u.refresh_token_enc),
            needs_reconnect=u.needs_reconnect,
        )
        for u in users
    ]
    rows.sort(key=lambda r: (r.cost_30d, r.cost_total), reverse=True)
    return rows


# ------------------------------------------------------------------ user and workspace detail


@dataclass
class RunRow:
    id: uuid.UUID
    kind: str
    status: str
    created_at: datetime
    duration_s: float | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    error_code: str | None


@dataclass
class EditRow:
    run_id: uuid.UUID
    text: str
    created_at: datetime
    status: str


@dataclass
class WorkspaceRow:
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    prompt: str
    status: str
    created_at: datetime
    last_synced_at: datetime | None
    record_count: int
    emails_processed: int
    emails_per_day: float  # matching emails processed per day, last 7 days
    cost_7d: float
    cost_30d: float
    cost_total: float
    runs: list[RunRow] = field(default_factory=list)
    edits: list[EditRow] = field(default_factory=list)


def _run_row(r: Run) -> RunRow:
    return RunRow(
        id=r.id,
        kind=r.kind.value,
        status=r.status.value,
        created_at=r.created_at,
        duration_s=duration_s(r),
        input_tokens=r.input_tokens,
        output_tokens=r.output_tokens,
        cost_usd=_f(r.cost_usd),
        error_code=error_code(r),
    )


def _edit_row(r: Run) -> EditRow | None:
    text = (r.input or {}).get("text")
    if r.kind != RunKind.EDIT or not isinstance(text, str):
        return None
    return EditRow(run_id=r.id, text=text, created_at=r.created_at, status=r.status.value)


async def _record_counts(session: AsyncSession, ws_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Records per workspace (`data` is {type: {id: record}}), counted in SQL so record
    values are never loaded into the admin process."""
    if not ws_ids:
        return {}
    rows = await session.execute(
        text(
            """
            SELECT w.id, count(r.key)
            FROM workspaces w
            CROSS JOIN LATERAL jsonb_each(
                CASE WHEN jsonb_typeof(w.data) = 'object' THEN w.data ELSE '{}'::jsonb END) t
            CROSS JOIN LATERAL jsonb_object_keys(
                CASE WHEN jsonb_typeof(t.value) = 'object' THEN t.value ELSE '{}'::jsonb END
            ) AS r(key)
            WHERE w.id = ANY(:ids) AND left(t.key, 1) <> '_'
            GROUP BY w.id
            """
        ),
        {"ids": ws_ids},
    )
    return {ws_id: int(n) for ws_id, n in rows}


async def _workspace_rows(
    session: AsyncSession, workspaces: list[Workspace], runs_limit: int
) -> list[WorkspaceRow]:
    ids = [w.id for w in workspaces]
    if not ids:
        return []
    since7 = datetime.now(UTC) - timedelta(days=7)
    processed = {
        ws_id: (int(total), int(recent or 0))
        for ws_id, total, recent in await session.execute(
            select(
                ProcessedMessage.workspace_id,
                func.count(),
                func.count().filter(ProcessedMessage.created_at >= since7),
            )
            .where(ProcessedMessage.workspace_id.in_(ids))
            .group_by(ProcessedMessage.workspace_id)
        )
    }
    costs = await _costs(session, LLMCall.workspace_id, [LLMCall.workspace_id.in_(ids)])
    records = await _record_counts(session, ids)
    rows = []
    for w in workspaces:
        runs = list(
            await session.scalars(
                select(Run)
                .where(Run.workspace_id == w.id)
                .order_by(Run.created_at.desc())
                .limit(runs_limit)
            )
        )
        total, recent = processed.get(w.id, (0, 0))
        c7, c30, ct = costs.get(w.id, (0.0, 0.0, 0.0))
        rows.append(
            WorkspaceRow(
                id=w.id,
                user_id=w.user_id,
                name=w.name,
                prompt=w.prompt,
                status=w.status.value,
                created_at=w.created_at,
                last_synced_at=w.last_synced_at,
                record_count=records.get(w.id, 0),
                emails_processed=total,
                emails_per_day=round(recent / 7, 1),
                cost_7d=c7,
                cost_30d=c30,
                cost_total=ct,
                runs=[_run_row(r) for r in runs],
                edits=[e for r in runs if (e := _edit_row(r)) is not None],
            )
        )
    return rows


async def _load_workspaces(session: AsyncSession, *where: Any) -> list[Workspace]:
    """Workspaces without their content columns (data, guide, app_html, config)."""
    return list(
        await session.scalars(
            select(Workspace)
            .options(
                load_only(
                    Workspace.id,
                    Workspace.user_id,
                    Workspace.name,
                    Workspace.prompt,
                    Workspace.status,
                    Workspace.created_at,
                    Workspace.last_synced_at,
                )
            )
            .where(*where)
            .order_by(Workspace.created_at)
        )
    )


@dataclass
class UserDetail:
    user: UserRow
    mailbox_daily: list[tuple[date, int | None]]
    workspaces: list[WorkspaceRow]


async def user_detail(session: AsyncSession, user_id: uuid.UUID) -> UserDetail | None:
    u = await session.get(User, user_id)
    if u is None:
        return None
    workspaces = await _load_workspaces(session, Workspace.user_id == user_id)
    ws_rows = await _workspace_rows(session, workspaces, RUNS_PER_WORKSPACE)
    costs = await _costs(
        session, LLMCall.user_id, [LLMCall.user_id == user_id, LLMCall.phase.not_in(STAFF_PHASES)]
    )
    c7, c30, ct = costs.get(user_id, (0.0, 0.0, 0.0))
    span = _days(30, _today() - timedelta(days=1))
    daily = dict(
        (
            await session.execute(
                select(MailboxDailyStat.date, MailboxDailyStat.messages_received).where(
                    MailboxDailyStat.user_id == user_id, MailboxDailyStat.date >= span[0]
                )
            )
        ).all()
    )
    processed = await session.scalar(
        select(func.count())
        .select_from(ProcessedMessage)
        .join(Workspace, Workspace.id == ProcessedMessage.workspace_id)
        .where(Workspace.user_id == user_id)
    )
    row = UserRow(
        id=u.id,
        email=u.email,
        name=" ".join(p for p in (u.first_name, u.last_name) if p) or u.name,
        created_at=u.created_at,
        last_active_at=(await _last_active(session, [user_id])).get(user_id),
        workspaces=len(workspaces),
        emails_processed=int(processed or 0),
        emails_received_per_day=(await _received_per_day(session, [user_id])).get(user_id),
        cost_7d=c7,
        cost_30d=c30,
        cost_total=ct,
        gmail_connected=bool(u.refresh_token_enc),
        needs_reconnect=u.needs_reconnect,
    )
    return UserDetail(user=row, mailbox_daily=[(d, daily.get(d)) for d in span], workspaces=ws_rows)


@dataclass
class WorkspaceDetail:
    workspace: WorkspaceRow
    owner_email: str
    days: int
    daily: list[tuple[date, float, int, int, int]]  # day, cost, tokens in, out, emails


async def workspace_detail(
    session: AsyncSession, workspace_id: uuid.UUID, days: int
) -> WorkspaceDetail | None:
    found = await _load_workspaces(session, Workspace.id == workspace_id)
    if not found:
        return None
    w = found[0]
    owner = await session.scalar(select(User.email).where(User.id == w.user_id))
    span = _days(days)
    start = _start(span[0])
    [row] = await _workspace_rows(session, [w], runs_limit=500)
    row.runs = [r for r in row.runs if r.created_at >= start]
    row.edits = [e for e in row.edits if e.created_at >= start]
    day = _day(LLMCall.created_at)
    cost = {
        d: (_f(c), int(i or 0), int(o or 0))
        for d, c, i, o in await session.execute(
            select(
                day,
                func.sum(LLMCall.cost_usd),
                func.sum(LLMCall.input_tokens),
                func.sum(LLMCall.output_tokens),
            )
            .where(LLMCall.workspace_id == workspace_id, LLMCall.created_at >= start)
            .group_by(day)
        )
    }
    pday = _day(ProcessedMessage.created_at)
    emails = dict(
        (
            await session.execute(
                select(pday, func.count())
                .where(
                    ProcessedMessage.workspace_id == workspace_id,
                    ProcessedMessage.created_at >= start,
                )
                .group_by(pday)
            )
        ).all()
    )
    daily = [(d, *cost.get(d, (0.0, 0, 0)), int(emails.get(d, 0))) for d in span]
    return WorkspaceDetail(workspace=row, owner_email=owner or "", days=days, daily=daily)
