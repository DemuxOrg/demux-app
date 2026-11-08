"""Workspace business logic.

Responsible for everything that can be done with workspaces: list, create (enforcing
the MVP limit of 2 per user), get, delete. Routes call these functions and stay thin.

HARD RULE: every query filters by `user_id`. A workspace owned by someone else is
reported as "not found" so its existence is never leaked.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.workspace import Workspace

MAX_WORKSPACES_PER_USER = 2


async def list_workspaces(session: AsyncSession, user_id: uuid.UUID) -> list[Workspace]:
    result = await session.scalars(
        select(Workspace).where(Workspace.user_id == user_id).order_by(Workspace.created_at)
    )
    return list(result)


async def create_workspace(
    session: AsyncSession, user_id: uuid.UUID, name: str, prompt: str
) -> Workspace:
    count = await session.scalar(
        select(func.count()).select_from(Workspace).where(Workspace.user_id == user_id)
    )
    if (count or 0) >= MAX_WORKSPACES_PER_USER:
        raise ConflictError(
            f"Workspace limit reached: you can have at most {MAX_WORKSPACES_PER_USER} workspaces."
        )
    workspace = Workspace(user_id=user_id, name=name, prompt=prompt)
    session.add(workspace)
    await session.flush()
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


async def delete_workspace(
    session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID
) -> None:
    workspace = await get_workspace(session, user_id, workspace_id)
    await session.delete(workspace)
    await session.flush()
