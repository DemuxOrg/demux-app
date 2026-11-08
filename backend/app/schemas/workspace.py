"""Pydantic schemas for the workspaces API.

Responsible for the request/response shapes at the API boundary only (models and
services never depend on these). They also define the OpenAPI schema from which the
frontend types are generated (`make gen-api`).
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.workspace import WorkspaceStatus


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=10_000)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prompt: str
    config: dict[str, Any]
    status: WorkspaceStatus
    last_refreshed_at: datetime | None
    created_at: datetime
    updated_at: datetime
