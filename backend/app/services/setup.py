"""Setup with the user while a workspace is built (frontend/theme.md §7.10, §7.15).

Two kinds of question moments, shown one at a time:
- **Look**, when the prompt doesn't say how the workspace should look (`look_state`
  "asking", set when the build run is created, `app/agent/look.py`). The answer goes to
  the interface designer, never to Demux's palettes.
- The design agent's **clarifying questions** (`ask_user`): one multiple-choice
  question per gap in the request, none when the request is precise. `ask_user` returns
  at once; `get_answers` collects them later.

The build run's `input` JSON holds the setup, one key per fact. The worker writes the
questions and their state through its persister; this service writes the user's
answers, one per request, merged into what is there (`input || {...}` at the top level,
`jsonb ||` inside `answers` and `answered_at`), so no writer overwrites another.
"""

import json
import uuid
from datetime import UTC, datetime
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
    answers = i.get("answers") or {}
    look_state = i.get("look_state", "none")  # runs created before the look moment
    return {
        "questions_state": i.get("questions_state", "deciding"),
        "questions": i.get("questions") or [],
        "answered": bool(answers),
        "answered_ids": sorted(answers),
        "look_state": look_state,
        "look_from_prompt": look_state == "from_prompt",
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


_MERGE = text(
    """UPDATE runs SET input = input
         || jsonb_build_object(
              'answers', COALESCE(input->'answers', '{}'::jsonb) || CAST(:answers AS jsonb),
              'answered_at', COALESCE(input->'answered_at', '{}'::jsonb) || CAST(:at AS jsonb))
       WHERE id = :id"""
)


async def update_setup(
    session: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    *,
    answers: dict[str, str] | None = None,
    look: str | None = None,
) -> Run:
    """Record the user's answer(s): clarifying answers by question id (merged into the
    ones already given) and/or the look. Each is accepted only while it is asked."""
    workspace = await get_workspace(session, user_id, workspace_id)
    run = await _active_build(session, workspace.id)
    current = run.input or {}
    now = datetime.now(UTC).isoformat()
    if look is not None:
        if current.get("look_state") != "asking":
            raise ConflictError("The look isn't being asked.")
        await session.execute(
            text("UPDATE runs SET input = input || CAST(:patch AS jsonb) WHERE id = :id"),
            {
                "patch": json.dumps({"look": look, "look_state": "answered", "look_at": now}),
                "id": run.id,
            },
        )
    if answers:
        ids = {q.get("id") for q in current.get("questions") or []}
        if current.get("questions_state") != "asking" or not ids:
            raise ConflictError("There are no questions to answer.")
        unknown = set(answers) - ids
        if unknown:
            raise ValidationError(f"Unknown question: {sorted(unknown)[0]}.")
        await session.execute(
            _MERGE,
            {
                "answers": json.dumps(answers),
                "at": json.dumps(dict.fromkeys(answers, now)),
                "id": run.id,
            },
        )
    await session.flush()
    await session.refresh(run)
    return run
