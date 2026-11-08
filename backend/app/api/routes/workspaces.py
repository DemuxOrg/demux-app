"""`/api/v1/workspaces` endpoints.

Responsible for the HTTP layer of workspaces: list, create, get, delete. Each handler
only parses input, calls app/services/workspaces.py with the current user's id, and
returns a schema. No business logic here.
"""

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.workspace import WorkspaceCreate, WorkspaceRead
from app.services import workspaces as service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceRead])
async def list_workspaces(session: SessionDep, user: CurrentUser):
    return await service.list_workspaces(session, user.id)


@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceCreate, session: SessionDep, user: CurrentUser):
    return await service.create_workspace(session, user.id, body.name, body.prompt)


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    return await service.get_workspace(session, user.id, workspace_id)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    await service.delete_workspace(session, user.id, workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
