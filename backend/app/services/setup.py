"""Setup with the user while a workspace is built (frontend/theme.md §7.10).

The build run's `input` JSON holds the setup, one key per fact. The worker writes the
questions and layout options (and their states) through its persister; this service
writes the user's answers. Both add keys with `input || {...}`, so neither overwrites the
other.
"""

import json
import uuid
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.palettes import PALETTE_IDS
from app.core.errors import ConflictError, ValidationError
from app.models.run import Run, RunKind, RunStatus
from app.services.workspaces import get_workspace


def setup_state(run: Run) -> dict[str, Any] | None:
    """The setup as the build screen needs it, from a build run's input."""
    if run.kind != RunKind.BUILD:
        return None
    i = run.input or {}
    look = i.get("look") or {}
    layout = i.get("layout") or {}
    return {
        "palette": look.get("palette") if look.get("palette") in PALETTE_IDS else None,
        "questions_state": i.get("questions_state", "deciding"),
        "questions": i.get("questions") or [],
        "answered": bool(i.get("answers")),
        "layout_state": i.get("layout_state", "waiting"),
        "layout_options": i.get("layout_options") or [],
        "layout_primary": i.get("layout_primary"),
        "layout_chosen": bool(layout.get("views")),
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
    palette: str | None = None,
    answers: dict[str, str] | None = None,
    layout: dict[str, Any] | None = None,
) -> Run:
    workspace = await get_workspace(session, user_id, workspace_id)
    run = await _active_build(session, workspace.id)
    current = run.input or {}
    patch: dict[str, Any] = {}
    if palette is not None:
        patch["look"] = {"palette": palette}
        workspace.palette = palette
    if answers is not None:
        ids = {q.get("id") for q in current.get("questions") or []}
        if current.get("questions_state") != "asking" or not ids:
            raise ConflictError("There are no questions to answer.")
        unknown = set(answers) - ids
        if unknown:
            raise ValidationError(f"Unknown question: {sorted(unknown)[0]}.")
        patch["answers"] = answers
    if layout is not None:
        ids = {o.get("id") for o in current.get("layout_options") or []}
        if current.get("layout_state") != "choosing" or not ids:
            raise ConflictError("There are no layouts to choose from.")
        views = [v for v in dict.fromkeys(layout["views"]) if v in ids]
        if not views or len(views) != len(set(layout["views"])):
            raise ValidationError("Choose layouts from the options offered.")
        if layout["primary"] not in views:
            raise ValidationError("The layout that opens first must be one you chose.")
        patch["layout"] = {"views": views, "primary": layout["primary"]}
    if patch:
        await session.execute(
            text("UPDATE runs SET input = input || CAST(:patch AS jsonb) WHERE id = :id"),
            {"patch": json.dumps(patch), "id": run.id},
        )
        await session.flush()
        await session.refresh(run)
    return run
