"""Usage accounting: what every LLM call cost, and how much mail each user receives.

- `llm_calls`: one row per call to the model provider, written by `app/agent/llm.py`
  (successful and failed attempts). It stores the unit prices used at call time, so a
  later change to `prices.yaml` never rewrites history. `runs.input_tokens`,
  `output_tokens` and `cost_usd` are running totals of the same numbers.
- `mailbox_daily_stats`: messages received per user per UTC day, counted by the worker
  from Gmail message ids only (no message is fetched).

No content lives here: ids, counts, tokens, prices and timings only.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin

# Values of `llm_calls.phase`.
PHASES = ("design", "batch", "app", "edit", "seed")


class LLMCall(IdMixin, Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        Index("ix_llm_calls_created_at", "created_at"),
        Index("ix_llm_calls_user_created", "user_id", "created_at"),
        Index("ix_llm_calls_workspace_created", "workspace_id", "created_at"),
    )

    # Runs and workspaces can be deleted; their cost history stays (SET NULL).
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    phase: Mapped[str] = mapped_column(Text, nullable=False)  # one of PHASES
    model: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # USD per million tokens, as priced when the call was made.
    input_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    cached_input_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    output_price: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False)  # ok | error
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MailboxDailyStat(Base):
    __tablename__ = "mailbox_daily_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    messages_received: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
