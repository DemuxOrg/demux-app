"""`eval_runs`: one run of the agent eval suite, started from /admin/evals.

The worker starts each queued run as its own process (`python -m eval.agent --job`),
which writes the score, its parts and the full report here. The report comes from the
synthetic mailboxes in `backend/eval/agent/scenarios/`, never from a user's inbox.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin


class EvalRunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvalRun(IdMixin, Base):
    __tablename__ = "eval_runs"

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[EvalRunStatus] = mapped_column(
        Enum(EvalRunStatus, name="eval_run_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=EvalRunStatus.QUEUED,
    )
    # Scenario id prefixes to run; empty means all of them.
    scenario_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default=text("'{}'")
    )
    repeats: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # What the score belongs to (eval/agent/runner.py `code_version`).
    commit: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    suite_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    build_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The Demux score (0-100), the spread across repeats, and its parts.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    spread: Mapped[float | None] = mapped_column(Float, nullable=True)
    parts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    guardrails: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # Per-scenario results and metrics (eval/agent/runner.py `run_suite`).
    report: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
