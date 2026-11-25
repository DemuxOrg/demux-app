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


# ------------------------------------------------------------------ evals
#
# Everything below comes from the eval suite: the synthetic mailboxes and expectations in
# `backend/eval/agent/scenarios/` (committed fixtures), never a user's inbox. Labels,
# check specs, check details and the agent's questions are fixture text.


class EvalScenarioInfo(_Out):
    id: str
    prompt: str  # fixture prompt
    steps: int
    vague: bool  # the build should ask clarifying questions


class EvalParts(_Out):
    retrieval: float | None = None  # email recall, 0-100
    coverage: float | None = None  # request coverage, 0-100
    correctness: float | None = None
    clarification: float | None = None


class EvalGuardrail(_Out):
    key: str
    label: str
    value: float | None
    target: float
    op: str  # "≥" or "≤"
    met: bool | None


class EvalRunRow(_Out):
    id: uuid.UUID
    status: str
    scenario_ids: list[str]
    repeats: int
    progress_done: int
    progress_total: int
    commit: str | None
    branch: str | None
    agent_hash: str | None
    suite_hash: str | None
    build_model: str | None
    sync_model: str | None
    score: float | None
    spread: float | None
    parts: EvalParts
    guardrails: list[EvalGuardrail]
    cost_usd: float
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class EvalsState(_Out):
    build_model: str  # what a new run will use
    scenarios: list[EvalScenarioInfo]
    runs: list[EvalRunRow]


class EvalRunCreate(BaseModel):
    repeats: int = Field(default=1, ge=1, le=5)
    scenario_ids: list[str] = Field(default_factory=list, max_length=50)  # empty: all


class EvalCheck(_Out):
    step: str
    kind: str
    passed: bool
    expected: str  # the check as written in scenario.yaml
    detail: str


class EvalAsk(_Out):
    step: str
    ask: str
    in_data: bool | None
    in_app: bool
    score: float
    detail: str


class EvalGroup(_Out):
    label: str
    thread_ids: list[str]
    recalled: bool


class EvalRetrieval(_Out):
    recall: float | None
    recalled: int
    total: int
    cited_threads: int
    cited_relevant: int
    groups: list[EvalGroup]


class EvalQuestion(_Out):
    question: str
    options: list[str]
    answer: str | None  # the scripted user's pick; none: the recommended option was used


class EvalClarify(_Out):
    expected: bool
    asked: bool
    on_topic: bool | None
    score: float
    questions: list[EvalQuestion]


class EvalStep(_Out):
    name: str
    kind: str
    error: str | None
    cost_usd: float
    input_tokens: int
    output_tokens: int
    latency_s: float
    record_count: int
    app_renders: bool
    checks: list[EvalCheck]


class EvalScenarioResult(_Out):
    id: str
    repeat: int
    prompt: str
    score: float  # 0-100
    parts: EvalParts
    retrieval: EvalRetrieval | None
    asks: list[EvalAsk]
    clarify: EvalClarify | None
    steps: list[EvalStep]


class EvalRunDetail(EvalRunRow):
    scenarios: list[EvalScenarioResult]
