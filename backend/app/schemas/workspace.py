"""Pydantic schemas for the workspaces, runs and auth APIs.

Request/response shapes at the API boundary only (models and services never depend on
these). They also define the OpenAPI schema from which the frontend types are generated
(`make gen-api`).
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.run import RunKind, RunStatus
from app.models.workspace import WorkspaceStatus


class Me(BaseModel):
    email: str  # login email (better-auth)
    name: str
    gmail_email: str | None  # the connected Gmail, may differ from `email`
    gmail_connected: bool
    needs_reconnect: bool


class WorkspaceCreate(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    name: str | None = Field(default=None, max_length=200)


class WorkspaceRename(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    prompt: str
    status: WorkspaceStatus
    last_synced_at: datetime | None
    record_counts: dict[str, int]
    created_at: datetime


class RunEvent(BaseModel):
    t: float
    phase: str
    tool: str | None = None
    label: str


class ActiveRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: RunKind
    status: RunStatus
    events: list[RunEvent]
    created_at: datetime


class WorkspaceDetail(BaseModel):
    id: uuid.UUID
    name: str
    prompt: str
    status: WorkspaceStatus
    data_version: int
    app_version: int
    last_synced_at: datetime | None
    record_counts: dict[str, int]
    queries: list[str]
    active_run: ActiveRun | None
    last_error: str | None
    can_undo: bool
    created_at: datetime


class AppDoc(BaseModel):
    html: str | None
    version: int


class AppShell(BaseModel):
    head: str


class DataDoc(BaseModel):
    data: dict[str, Any]
    version: int


class GuideDoc(BaseModel):
    guide: str
    queries: list[str]


class ChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID | None
    record_type: str
    record_id: str
    op: str
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    thread_ids: list[str]
    created_at: datetime


class RunRead(BaseModel):
    id: uuid.UUID
    kind: RunKind
    status: RunStatus
    input_text: str | None
    summary: str | None
    error: str | None
    cost_usd: float
    input_tokens: int
    output_tokens: int
    events: list[RunEvent]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_s: float | None


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class RunCreated(BaseModel):
    run_id: uuid.UUID
