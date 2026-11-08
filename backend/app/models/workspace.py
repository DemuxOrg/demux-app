"""`workspaces` table.

Responsible for the Workspace model: a user's natural-language request (`prompt`)
plus its build state. `config` (JSONB) will later hold planned fields, Gmail queries
and the display component. Deleting a user cascades to their workspaces.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class WorkspaceStatus(enum.StrEnum):
    DRAFT = "draft"
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"


class Workspace(IdMixin, TimestampMixin, Base):
    __tablename__ = "workspaces"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(
            WorkspaceStatus,
            name="workspace_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
        default=WorkspaceStatus.DRAFT,
        server_default=WorkspaceStatus.DRAFT.value,
    )
    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
