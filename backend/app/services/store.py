"""Workspace data edits, snapshots and undo.

Pure part (no DB): `apply_save` / `apply_delete` validate and apply agent edits to the
data document (§2.1 of the build spec) and return the change rows to record.

DB part: persist data + changes in one transaction, snapshots (keep 10), undo,
processed messages. Every function that takes a `user_id` scopes through
`workspaces.user_id`; the worker-side helpers take a workspace id it already owns.
"""

import copy
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.models.run import Change, ProcessedMessage, Run, RunStatus, Snapshot
from app.models.workspace import Workspace

MAX_TYPES = 5
MAX_RECORDS = 500
MAX_FIELDS = 20
MAX_STR = 2000
MAX_SOURCES = 10
SNAPSHOTS_KEPT = 10

ID_RE = re.compile(r"^[a-z0-9-]{1,80}$")
TYPE_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


class DataError(ValueError):
    """An agent edit broke a data rule. The message goes back to the model."""


@dataclass
class ChangeRow:
    record_type: str
    record_id: str
    op: str  # create | update | delete
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    source_message_ids: list[str] = field(default_factory=list)


def public_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if not k.startswith("_")}


def count_records(data: dict[str, Any]) -> int:
    return sum(len(v) for v in data.values() if isinstance(v, dict))


def _check_value(name: str, value: Any) -> None:
    if value is None or isinstance(value, bool | int | float):
        return
    if isinstance(value, str):
        if len(value) > MAX_STR:
            raise DataError(f"field '{name}': string longer than {MAX_STR} chars")
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, list | dict):
                raise DataError(f"field '{name}': arrays must be flat (primitives only)")
            _check_value(name, item)
        return
    raise DataError(f"field '{name}': value must be a string, number, boolean, null or flat array")


def apply_save(
    data: dict[str, Any],
    record_type: str,
    records: list[dict[str, Any]],
    *,
    seen_messages: dict[str, str],
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[ChangeRow]]:
    """Validate and merge `records` into a copy of `data`.

    `seen_messages` maps every message id the agent received in this run to its thread
    id. Returns (new_data, per-record results, change rows). Raises DataError (nothing
    applied) if any record breaks a rule.
    """
    if not isinstance(record_type, str) or not TYPE_RE.match(record_type):
        raise DataError("record_type must be snake_case: lowercase letters, digits, underscores")
    if not isinstance(records, list) or not records:
        raise DataError("records must be a non-empty list")
    now_s = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    new = copy.deepcopy(data)
    if record_type not in new and len(new) >= MAX_TYPES:
        raise DataError(f"at most {MAX_TYPES} record types per workspace")
    bucket: dict[str, Any] = new.setdefault(record_type, {})

    errors: list[str] = []
    results: list[dict[str, Any]] = []
    changes: list[ChangeRow] = []
    for i, rec in enumerate(records):
        try:
            if not isinstance(rec, dict):
                raise DataError("each record must be an object {id, fields, source_message_ids}")
            rid = rec.get("id")
            fields = rec.get("fields")
            sources = rec.get("source_message_ids")
            if not isinstance(rid, str) or not ID_RE.match(rid):
                raise DataError("id must match [a-z0-9-]{1,80} (lowercase slug)")
            if not isinstance(fields, dict):
                raise DataError("fields must be an object")
            if not isinstance(sources, list) or not sources:
                raise DataError("source_message_ids: at least one message id is required")
            unknown = [s for s in sources if s not in seen_messages]
            if unknown:
                raise DataError(
                    "source_message_ids must be messages you received in this run; unknown: "
                    + ", ".join(str(u) for u in unknown[:5])
                )
            for name, value in fields.items():
                if not isinstance(name, str) or name.startswith("_"):
                    raise DataError(f"field '{name}': keys starting with '_' are reserved")
                if not FIELD_RE.match(name):
                    raise DataError(f"field '{name}': names must be snake_case")
                _check_value(name, value)

            existing = bucket.get(rid)
            before = public_fields(existing) if existing else None
            merged = dict(existing or {})
            merged.update(fields)
            after = public_fields(merged)
            if len(after) > MAX_FIELDS:
                raise DataError(f"at most {MAX_FIELDS} fields per record")
            old_sources = list((existing or {}).get("_sources", []))
            known = {s["message_id"] for s in old_sources}
            for mid in sources:
                if mid in known:
                    old_sources = [s for s in old_sources if s["message_id"] != mid]
                old_sources.append({"message_id": mid, "thread_id": seen_messages[mid]})
            merged["_sources"] = old_sources[-MAX_SOURCES:]

            if existing is None:
                merged["_updated_at"] = now_s
                bucket[rid] = merged
                results.append({"id": rid, "status": "created"})
                changes.append(ChangeRow(record_type, rid, "create", None, after, list(sources)))
            else:
                changed = sorted(
                    k
                    for k in set(before or {}) | set(after)
                    if (before or {}).get(k) != after.get(k)
                )
                if changed:
                    merged["_updated_at"] = now_s
                    changes.append(
                        ChangeRow(record_type, rid, "update", before, after, list(sources))
                    )
                bucket[rid] = merged
                results.append(
                    {"id": rid, "status": "updated" if changed else "unchanged", "fields": changed}
                )
        except DataError as e:
            errors.append(f"record {i} ({rec.get('id') if isinstance(rec, dict) else '?'}): {e}")
    if errors:
        raise DataError("; ".join(errors) + ". Nothing was saved; fix and retry.")
    if count_records(new) > MAX_RECORDS:
        raise DataError(f"at most {MAX_RECORDS} records per workspace")
    return new, results, changes


def apply_delete(
    data: dict[str, Any], record_type: str, ids: list[str]
) -> tuple[dict[str, Any], list[str], list[ChangeRow]]:
    if record_type not in data:
        raise DataError(f"unknown record type '{record_type}'")
    if not isinstance(ids, list) or not ids:
        raise DataError("ids must be a non-empty list")
    new = copy.deepcopy(data)
    missing = [i for i in ids if i not in new[record_type]]
    if missing:
        raise DataError("unknown ids: " + ", ".join(str(m) for m in missing[:10]))
    changes = []
    for rid in ids:
        rec = new[record_type].pop(rid)
        changes.append(ChangeRow(record_type, rid, "delete", public_fields(rec), None, []))
    if not new[record_type]:
        del new[record_type]
    return new, list(ids), changes


# ---------------------------------------------------------------- DB helpers


async def persist_data(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID | None,
    data: dict[str, Any],
    changes: list[ChangeRow],
) -> int:
    """Write data, bump data_version, append change rows. Caller commits."""
    version = await session.scalar(
        update(Workspace)
        .where(Workspace.id == workspace_id)
        .values(data=data, data_version=Workspace.data_version + 1)
        .returning(Workspace.data_version)
    )
    if changes:
        await session.execute(
            insert(Change),
            [
                {
                    "workspace_id": workspace_id,
                    "run_id": run_id,
                    "record_type": c.record_type,
                    "record_id": c.record_id,
                    "op": c.op,
                    "before": c.before,
                    "after": c.after,
                    "source_message_ids": c.source_message_ids,
                }
                for c in changes
            ],
        )
    return int(version or 0)


async def take_snapshot(
    session: AsyncSession, workspace_id: uuid.UUID, run_id: uuid.UUID | None
) -> None:
    ws = await session.get(Workspace, workspace_id)
    if ws is None:
        raise NotFoundError("Workspace not found.")
    session.add(
        Snapshot(
            workspace_id=workspace_id,
            run_id=run_id,
            data=copy.deepcopy(ws.data),
            guide=ws.guide,
            app_html=ws.app_html,
            config=copy.deepcopy(ws.config),
        )
    )
    await session.flush()
    keep = select(Snapshot.id).where(Snapshot.workspace_id == workspace_id)
    keep = keep.order_by(Snapshot.created_at.desc()).limit(SNAPSHOTS_KEPT)
    await session.execute(
        delete(Snapshot).where(Snapshot.workspace_id == workspace_id, Snapshot.id.not_in(keep))
    )


async def _restore(session: AsyncSession, ws: Workspace, snap: Snapshot) -> None:
    ws.data = copy.deepcopy(snap.data)
    ws.guide = snap.guide
    ws.app_html = snap.app_html
    ws.config = copy.deepcopy(snap.config)
    ws.data_version += 1
    ws.app_version += 1


async def restore_run_snapshot(
    session: AsyncSession, workspace_id: uuid.UUID, run_id: uuid.UUID
) -> bool:
    """Restore the snapshot taken at the start of `run_id` (failed edit)."""
    ws = await session.get(Workspace, workspace_id)
    snap = await session.scalar(
        select(Snapshot)
        .where(Snapshot.workspace_id == workspace_id, Snapshot.run_id == run_id)
        .order_by(Snapshot.created_at.desc())
        .limit(1)
    )
    if ws is None or snap is None:
        return False
    await _restore(session, ws, snap)
    await session.delete(snap)
    await session.flush()
    return True


async def undo(session: AsyncSession, user_id: uuid.UUID, workspace_id: uuid.UUID) -> Workspace:
    ws = await session.scalar(
        select(Workspace)
        .where(Workspace.id == workspace_id, Workspace.user_id == user_id)
        .with_for_update()
    )
    if ws is None:
        raise NotFoundError("Workspace not found.")
    active = await session.scalar(
        select(Run.id).where(
            Run.workspace_id == workspace_id,
            Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    )
    if active is not None:
        raise ConflictError("Wait for the current run to finish before undoing.")
    snap = await session.scalar(
        select(Snapshot)
        .where(Snapshot.workspace_id == workspace_id)
        .order_by(Snapshot.created_at.desc())
        .limit(1)
    )
    if snap is None:
        raise ConflictError("Nothing to undo.")
    await _restore(session, ws, snap)
    await session.delete(snap)
    session.add(
        Change(
            workspace_id=workspace_id,
            run_id=None,
            record_type="_workspace",
            record_id="undo",
            op="update",
            before=None,
            after=None,
            source_message_ids=[],
        )
    )
    await session.flush()
    return ws


async def processed_message_ids(session: AsyncSession, workspace_id: uuid.UUID) -> set[str]:
    rows = await session.scalars(
        select(ProcessedMessage.message_id).where(ProcessedMessage.workspace_id == workspace_id)
    )
    return set(rows)


async def processed_thread_ids(session: AsyncSession, workspace_id: uuid.UUID) -> list[str]:
    rows = await session.scalars(
        select(ProcessedMessage.thread_id)
        .where(ProcessedMessage.workspace_id == workspace_id)
        .distinct()
    )
    return list(rows)


async def mark_processed(
    session: AsyncSession,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID | None,
    pairs: list[tuple[str, str]],
) -> None:
    if not pairs:
        return
    stmt = pg_insert(ProcessedMessage).values(
        [
            {"workspace_id": workspace_id, "message_id": m, "thread_id": t, "run_id": run_id}
            for m, t in pairs
        ]
    )
    await session.execute(stmt.on_conflict_do_nothing())
