"""Admin-only tables.

- `admin_audit`: one row per admin request (who, which route, which target, when).
- `demo_seeds`: one request to fill the demo inbox with synthetic threads written by the
  LLM (admin page "Demo inbox"); the worker picks queued ones up. Only counts are kept,
  never the generated text.
"""

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin


class AdminAudit(IdMixin, Base):
    __tablename__ = "admin_audit"

    admin_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Kept as text so the trail survives the admin's account.
    admin_email: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # route path template
    target: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )


class DemoSeedStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class DemoSeed(IdMixin, Base):
    __tablename__ = "demo_seeds"

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)  # typed by the admin
    thread_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[DemoSeedStatus] = mapped_column(
        Enum(
            DemoSeedStatus, name="demo_seed_status", values_callable=lambda e: [m.value for m in e]
        ),
        nullable=False,
        default=DemoSeedStatus.QUEUED,
    )
    threads_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    messages_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
