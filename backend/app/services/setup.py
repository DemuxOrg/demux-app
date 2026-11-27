"""Setup with the user while a workspace is built (frontend/theme.md §7.10).

The only setup step is the design agent's clarifying questions (`ask_user`): one
multiple-choice question per gap in the request, none when the request is precise.
The build run's `input` JSON holds the setup, one key per fact. The worker writes the
questions and their state through its persister; this service writes the user's answers.
Both add keys with `input || {...}`, so neither overwrites the other.
"""

import json
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, ValidationError
from app.models.run import Run, RunKind, RunStatus
from app.services.workspaces import get_workspace


def setup_state(run: Run) -> dict[str, Any] | None:
    """The setup as the build screen needs it, from a build run's input."""
    if run.kind != RunKind.BUILD:
        return None
    i = run.input or {}
    return {
        "questions_state": i.get("questions_state", "deciding"),
        "questions": i.get("questions") or [],
        "answered": bool(i.get("answers")),
    }


async def _active_build(session: AsyncSession, workspace_id: uuid.UUID) -> Run:
    run = await session.scalar(
        select(Run).where(
            Run.workspace_id == workspace_id,
            Run.kind == RunKind.BUILD,
            Run.status.in_([RunStatus.QUEUED, RunStatus.RUNNING]),
        )
    )
    if run is None:
        raise ConflictError("This workspace is not being built.")
    return run


async def update_setup(
    session: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    *,
    answers: dict[str, str],
) -> Run:
    workspace = await get_workspace(session, user_id, workspace_id)
    run = await _active_build(session, workspace.id)
    current = run.input or {}
    ids = {q.get("id") for q in current.get("questions") or []}
    if current.get("questions_state") != "asking" or not ids:
        raise ConflictError("There are no questions to answer.")
    unknown = set(answers) - ids
    if unknown:
        raise ValidationError(f"Unknown question: {sorted(unknown)[0]}.")
    await session.execute(
        text("UPDATE runs SET input = input || CAST(:patch AS jsonb) WHERE id = :id"),
        {"patch": json.dumps({"answers": answers}), "id": run.id},
    )
    await session.flush()
    await session.refresh(run)
    return run
