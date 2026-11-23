"""Response shapes for `/api/v1/admin`.

Privacy: every field here is an id, a count, tokens, a cost, a status, a date, or text
the user typed (workspace prompt, edit messages). `tests/test_admin.py` keeps an
allowlist of these field names: adding one fails the test until it is reviewed there.
Never add email content, subjects, senders, record values, the guide or app HTML.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DailyKeyCost(_Out):
    date: date
    key: str  # a phase or a model
    cost_usd: float


class DailyTokens(_Out):
    date: date
    input_tokens: int
    output_tokens: int


class DailyUserCost(_Out):
    date: date
    active_users: int
    p50_usd: float
    p95_usd: float


class DailyFailures(_Out):
    date: date
    finished: int
    failed: int


class AdminOverview(_Out):
    days: int
    start: date
    end: date
    active_users: int
    total_users: int
    workspaces: int
    new_workspaces: int
    builds: int
    syncs: int
    edits: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    failed_runs: int
    finished_runs: int
    cost_by_phase: list[DailyKeyCost]
    cost_by_model: list[DailyKeyCost]
    tokens: list[DailyTokens]
    cost_per_user: list[DailyUserCost]
    failures: list[DailyFailures]


class AdminUserRow(_Out):
    id: uuid.UUID
    email: str  # login email
    name: str
    created_at: datetime
    last_active_at: datetime | None
    workspaces: int
    emails_processed: int
    emails_received_per_day: float | None  # 7-day average, None until counted
    cost_7d: float
    cost_30d: float
    cost_total: float
    gmail_connected: bool
    needs_reconnect: bool


class AdminRun(_Out):
    id: uuid.UUID
    kind: str
    status: str
    created_at: datetime
    duration_s: float | None
    input_tokens: int
    output_tokens: int
    cost_usd: float
    error_code: str | None


class AdminEdit(_Out):
    run_id: uuid.UUID
    text: str  # what the user typed in the edit chat
    created_at: datetime
    status: str


class AdminWorkspace(_Out):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    prompt: str
    status: str
    created_at: datetime
    last_synced_at: datetime | None
    record_count: int
    emails_processed: int
    emails_per_day: float
    cost_7d: float
    cost_30d: float
    cost_total: float
    runs: list[AdminRun]
    edits: list[AdminEdit]


class DailyCount(_Out):
    date: date
    count: int | None  # None: not counted that day


class AdminUserDetail(_Out):
    user: AdminUserRow
    mailbox_daily: list[DailyCount]
    workspaces: list[AdminWorkspace]


class DailyWorkspaceUsage(_Out):
    date: date
    cost_usd: float
    input_tokens: int
    output_tokens: int
    emails: int


class AdminWorkspaceDetail(_Out):
    workspace: AdminWorkspace
    owner_email: str
    days: int
    daily: list[DailyWorkspaceUsage]


class DemoSeedRead(_Out):
    id: uuid.UUID
    prompt: str  # typed by the admin
    thread_count: int
    status: str
    threads_created: int
    messages_created: int
    cost_usd: float
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class DemoInboxState(_Out):
    configured: bool
    inbox_email: str | None
    model: str
    seeds: list[DemoSeedRead]


class DemoSeedCreate(BaseModel):
    prompt: str = Field(min_length=10, max_length=2000)
    thread_count: int = Field(default=15, ge=3, le=40)


class DemoCleanup(_Out):
    removed: int
