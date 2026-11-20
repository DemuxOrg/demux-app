"""Workspace business logic.

Responsible for everything that can be done with workspaces: list, create (enforcing
the MVP limit of 2 per user, and enqueuing the build), get, rename, delete, rebuild.
Routes call these functions and stay thin.

HARD RULE: every query filters by `user_id`. A workspace owned by someone else is
reported as "not found" so its existence is never leaked.
"""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google import gmail_connected
from app.core.errors import AppError, ConflictError, NotFoundError
from app.models.run import ProcessedMessage, RunKind
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceStatus
from app.services import runs

MAX_WORKSPACES_PER_USER = 2


class ReconnectRequiredError(AppError):
    status_code = 409
    code = "reconnect_required"


class GmailNotConnectedError(AppError):
    status_code = 409
    code = "gmail_not_connected"


async def list_workspaces(session: AsyncSession, user_id: uuid.UUID) -> list[Workspace]:
    result = await session.scalars(
        select(Workspace).where(Workspace.user_id == user_id).order_by(Workspace.created_at)
    )
    return list(result)


def record_counts(workspace: Workspace) -> dict[str, int]:
    return {t: len(r) for t, r in (workspace.data or {}).items() if isinstance(r, dict)}


async def create_workspace(
    session: AsyncSession,
    user_id: uuid.UUID,
    prompt: str,
    name: str | None = None,
    *,
    enqueue_build: bool = True,
) -> Workspace:
    user = await session.get(User, user_id)
    if user is not None and not gmail_connected(user):
        raise GmailNotConnectedError("Connect Gmail before creating a workspace.")
    if user is not None and user.needs_reconnect:
        raise ReconnectRequiredError("Reconnect Gmail before creating a workspace.")
    count = await session.scalar(
        select(func.count()).select_from(Workspace).where(Workspace.user_id == user_id)
    )
    if (count or 0) >= MAX_WORKSPACES_PER_USER:
        raise ConflictError(
            f"Workspace limit reached: you can have at most {MAX_WORKSPACES_PER_USER} workspaces."
        )
    prompt = prompt.strip()
    workspace = Workspace(
        user_id=user_id,
        name=(name or prompt[:60]).strip() or "Workspace",
        prompt=prompt,
        status=WorkspaceStatus.BUILDING if enqueue_build else WorkspaceStatus.DRAFT,
    )
    session.add(workspace)
    await session.flush()
    if enqueue_build:
        await runs.enqueue(session, workspace.id, RunKind.BUILD)
    await session.refresh(workspace)
    return workspace


async def get_workspace(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> Workspace:
    workspace = await session.scalar(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
    )
    if workspace is None:
        raise NotFoundError("Workspace not found.")
    return workspace


async def rename_workspace(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID, name: str
) -> Workspace:
    workspace = await get_workspace(session, user_id, workspace_id)
    workspace.name = name.strip()
    await session.flush()
    await session.refresh(workspace)
    return workspace


async def delete_workspace(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    workspace = await get_workspace(session, user_id, workspace_id)
    await session.delete(workspace)
    await session.flush()


async def rebuild_workspace(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> Workspace:
    """'Try again' after a failed build: reset content and enqueue a new build."""
    workspace = await get_workspace(session, user_id, workspace_id)
    user = await session.get(User, user_id)
    if user is not None and user.needs_reconnect:
        raise ReconnectRequiredError("Reconnect Gmail first.")
    await runs.enqueue(session, workspace.id, RunKind.BUILD)
    workspace.status = WorkspaceStatus.BUILDING
    workspace.last_error = None
    workspace.data = {}
    workspace.guide = ""
    workspace.config = {}
    workspace.app_html = None
    workspace.data_version += 1
    workspace.app_version += 1
    await session.execute(
        delete(ProcessedMessage).where(ProcessedMessage.workspace_id == workspace.id)
    )
    await session.flush()
    await session.refresh(workspace)
    return workspace
