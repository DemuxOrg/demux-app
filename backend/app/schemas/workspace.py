"""Pydantic schemas for the workspaces, runs and auth APIs.

Request/response shapes at the API boundary only (models and services never depend on
these). They also define the OpenAPI schema from which the frontend types are generated
(`make gen-api`).
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.agent.palettes import PaletteId
from app.models.run import RunKind, RunStatus
from app.models.workspace import WorkspaceStatus


class AccessInfo(BaseModel):
    """Why the user may (or may not) use Demux (app/services/access.py)."""

    status: Literal["admin", "subscription", "grant", "trial", "none"]
    ends_at: datetime | None = None  # trial end or free-access expiry
    subscribe_url: str | None = None  # "trial" / "none": where to subscribe


class Me(BaseModel):
    email: str  # login email (better-auth)
    name: str
    first_name: str  # asked at sign-up; "" for accounts created before that
    last_name: str
    gmail_email: str | None  # the connected Gmail, may differ from `email`
    gmail_connected: bool
    needs_reconnect: bool
    is_admin: bool = False  # may open /admin
    access: AccessInfo  # "none": the app answers 402 and shows the subscribe screen


PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class MeUpdate(BaseModel):
    first_name: PersonName
    last_name: PersonName


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
    # Structured progress (reading emails): threads read so far and in total.
    done: int | None = None
    total: int | None = None


class SetupQuestion(BaseModel):
    id: str
    question: str
    options: list[str]
    recommended: int


class SetupState(BaseModel):
    """Where a build's clarifying questions stand (frontend/theme.md §7.10)."""

    questions_state: Literal["deciding", "asking", "answered", "timed_out", "none"]
    questions: list[SetupQuestion]
    answered: bool  # the user sent answers (the build may not have read them yet)


Answer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]


class SetupUpdate(BaseModel):
    """The user's answers to the clarifying questions, by question id."""

    answers: dict[str, Answer] = Field(min_length=1, max_length=5)


class ActiveRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: RunKind
    status: RunStatus
    events: list[RunEvent]
    created_at: datetime
    setup: SetupState | None = None  # build runs only


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
    palette: PaletteId
    active_run: ActiveRun | None
    last_error: str | None
    can_undo: bool
    created_at: datetime


class AppDoc(BaseModel):
    html: str | None
    version: int
    runtime: Literal["v1", "v2"]  # v2: a kit app (the shell for ?runtime=v2)


class PaletteInfo(BaseModel):
    """What the frontend needs to draw a palette tile (frontend/theme.md §7.10)."""

    id: PaletteId
    name: str
    accent: str
    accent_ink: str
    accent_soft: str
    series: list[str]  # series 1-5, hex


class AppShell(BaseModel):
    head: str
    palettes: list[PaletteInfo]


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
