"""Run context shared by the loop, the tools and the flows.

`WorkspaceState` is the in-memory copy of what the agent edits. Every successful tool
write goes through a `Persister`, which stores it (Postgres for real runs, memory/files
for the CLI and eval). The tools never touch the DB directly.
"""

import copy
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from app.mail.base import Mailbox
from app.services.store import ChangeRow


@dataclass
class WorkspaceState:
    prompt: str
    name: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    guide: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    app_html: str | None = None
    data_version: int = 0
    app_version: int = 0
    last_synced_at: datetime | None = None

    @property
    def queries(self) -> list[str]:
        return list(self.config.get("queries", []))

    def copy(self) -> "WorkspaceState":
        return copy.deepcopy(self)


class BudgetExceeded(Exception):
    pass


class Persister(Protocol):
    async def save_data(self, state: WorkspaceState, changes: list[ChangeRow]) -> None: ...
    async def save_guide(self, state: WorkspaceState) -> None: ...
    async def save_name(self, state: WorkspaceState) -> None:
        """Store `state.name`, unless the user has already renamed the workspace."""
        ...

    async def save_config(self, state: WorkspaceState) -> None: ...
    async def save_app(self, state: WorkspaceState) -> None: ...
    async def save_synced(self, state: WorkspaceState) -> None: ...
    async def add_event(self, event: dict[str, Any]) -> None: ...
    async def add_usage(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        """Record usage; raise BudgetExceeded when a run or daily cap is passed."""
        ...

    async def processed_ids(self) -> set[str]: ...
    async def processed_thread_ids(self) -> list[str]: ...
    async def mark_processed(self, pairs: list[tuple[str, str]]) -> None: ...
    async def snapshot(self) -> None: ...
    async def restore_snapshot(self) -> None: ...


@dataclass
class RunContext:
    state: WorkspaceState
    mailbox: Mailbox
    persister: Persister
    run_id: str
    now: datetime = field(default_factory=lambda: datetime.now(UTC))
    phase: str = ""
    # message id -> thread id, for every message the agent received in this run
    seen_messages: dict[str, str] = field(default_factory=dict)
    # thread ids the agent may read (returned by a search or given in the input)
    known_threads: set[str] = field(default_factory=set)
    backfill_requested: bool = False
    app_written: bool = False
    guide_changed: bool = False
    data_changed: bool = False
    finish_summary: str | None = None
    lookback_days: int = 90
    max_build_threads: int = 150
    inline_max_chars: int = 120_000
    # message id -> date, for the newest-wins guard during parallel backfill
    message_dates: dict[str, datetime] = field(default_factory=dict)
    # When true (parallel backfill), older emails may only fill empty fields.
    older_fill_only: bool = False
    # Design-phase budget: keeps the first phase short and its context small.
    design_reads: int = 0
    design_searches: int = 0

    def child(self, phase: str, **overrides: Any) -> "RunContext":
        """A context for one concurrent phase: shares state, mailbox, persister and the
        seen-message maps, but has its own phase and per-phase flags."""
        from dataclasses import replace

        return replace(
            self,
            phase=phase,
            finish_summary=None,
            app_written=False,
            guide_changed=False,
            data_changed=False,
            **overrides,
        )

    @property
    def window_start(self) -> datetime:
        from datetime import timedelta

        return self.now - timedelta(days=self.lookback_days)


class MemoryPersister:
    """Keeps everything in memory; optionally saves the state to a folder (CLI, eval)."""

    def __init__(self, out_dir: Path | None = None, max_usd: float = 1e9):
        self.out_dir = out_dir
        self.events: list[dict[str, Any]] = []
        self.changes: list[ChangeRow] = []
        self.processed: dict[str, str] = {}
        self.snapshots: list[WorkspaceState] = []
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = 0.0
        self.max_usd = max_usd
        self.state: WorkspaceState | None = None

    async def save_data(self, state: WorkspaceState, changes: list[ChangeRow]) -> None:
        state.data_version += 1
        self.changes += changes
        self._dump(state)

    async def save_guide(self, state: WorkspaceState) -> None:
        self._dump(state)

    async def save_name(self, state: WorkspaceState) -> None:
        self._dump(state)

    async def save_config(self, state: WorkspaceState) -> None:
        self._dump(state)

    async def save_app(self, state: WorkspaceState) -> None:
        state.app_version += 1
        self._dump(state)

    async def save_synced(self, state: WorkspaceState) -> None:
        self._dump(state)

    async def add_event(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def add_usage(self, input_tokens: int, output_tokens: int, cost: float) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost += cost
        if self.cost > self.max_usd:
            raise BudgetExceeded(f"run cost ${self.cost:.2f} exceeds ${self.max_usd:.2f}")

    async def processed_ids(self) -> set[str]:
        return set(self.processed)

    async def processed_thread_ids(self) -> list[str]:
        return sorted(set(self.processed.values()))

    async def mark_processed(self, pairs: list[tuple[str, str]]) -> None:
        for m, t in pairs:
            self.processed[m] = t
        if self.state is not None:
            self._dump(self.state)

    async def snapshot(self) -> None:
        if self.state is not None:
            self.snapshots.append(self.state.copy())

    async def restore_snapshot(self) -> None:
        if self.state is not None and self.snapshots:
            snap = self.snapshots.pop()
            self.state.data, self.state.guide = snap.data, snap.guide
            self.state.config, self.state.app_html = snap.config, snap.app_html

    # -- files

    def _dump(self, state: WorkspaceState) -> None:
        self.state = state
        if self.out_dir is None:
            return
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / "state.json").write_text(
            json.dumps(
                {
                    "prompt": state.prompt,
                    "name": state.name,
                    "data": state.data,
                    "guide": state.guide,
                    "config": state.config,
                    "last_synced_at": state.last_synced_at.isoformat()
                    if state.last_synced_at
                    else None,
                    "processed": self.processed,
                },
                indent=2,
            )
        )
        (self.out_dir / "guide.md").write_text(state.guide)
        if state.app_html:
            (self.out_dir / "app.html").write_text(state.app_html)

    @classmethod
    def load(cls, out_dir: Path) -> tuple["MemoryPersister", WorkspaceState]:
        raw = json.loads((out_dir / "state.json").read_text())
        p = cls(out_dir)
        p.processed = raw.get("processed", {})
        app = out_dir / "app.html"
        state = WorkspaceState(
            prompt=raw["prompt"],
            name=raw.get("name", ""),
            data=raw["data"],
            guide=raw["guide"],
            config=raw["config"],
            app_html=app.read_text() if app.exists() else None,
            last_synced_at=datetime.fromisoformat(raw["last_synced_at"])
            if raw.get("last_synced_at")
            else None,
        )
        p.state = state
        return p, state
