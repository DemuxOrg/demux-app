"""`workspaces` table.

Responsible for the Workspace model: the user's prompt plus the three things the agent
edits — `app_html` (the generated interface), `data` (records by type, see the build
spec §2.1) and `guide` (the agent's own notes). `config` holds `{"queries": [...]}`.
Deleting a user cascades to their workspaces.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


def provisional_name(prompt: str) -> str:
    """The name a workspace gets at creation, until the design phase names it."""
    return prompt.strip()[:60].strip() or "Workspace"


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
    guide: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    app_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    data_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    app_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
