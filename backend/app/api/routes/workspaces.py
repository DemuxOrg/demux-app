"""`/api/v1/workspaces` endpoints (build spec §8).

Each handler parses input, calls a service with the current user's id, and returns a
schema. Unknown or foreign ids are 404. Users without access (no subscription, trial or
free access) get 402 `subscription_required` from every `/workspaces` route.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import exists, select

from app.agent.palettes import PALETTES, valid_palette
from app.agent.shell import app_runtime, shell_head
from app.api.deps import CurrentUser, SessionDep, get_entitled_user
from app.models.run import Change, Run, RunKind
from app.models.workspace import Workspace
from app.schemas.workspace import (
    ActiveRun,
    AppDoc,
    AppShell,
    ChangeRead,
    DataDoc,
    GuideDoc,
    MessageCreate,
    PaletteInfo,
    RunCreated,
    RunRead,
    SetupState,
    SetupUpdate,
    WorkspaceCreate,
    WorkspaceDetail,
    WorkspaceRename,
    WorkspaceSummary,
)
from app.services import runs as runs_service
from app.services import setup as setup_service
from app.services import store
from app.services import workspaces as service

# Only users with access (subscription, trial, free access, admin): 402 otherwise.
router = APIRouter(
    prefix="/workspaces", tags=["workspaces"], dependencies=[Depends(get_entitled_user)]
)
shell_router = APIRouter(tags=["workspaces"])


def _summary(w: Workspace) -> WorkspaceSummary:
    return WorkspaceSummary(
        id=w.id,
        name=w.name,
        prompt=w.prompt,
        status=w.status,
        last_synced_at=w.last_synced_at,
        record_counts=service.record_counts(w),
        created_at=w.created_at,
    )


def _run(r: Run) -> RunRead:
    duration = (
        (r.finished_at - r.started_at).total_seconds() if r.finished_at and r.started_at else None
    )
    return RunRead(
        id=r.id,
        kind=r.kind,
        status=r.status,
        input_text=r.input.get("text") if r.input else None,
        summary=r.summary,
        error=r.error,
        cost_usd=float(r.cost_usd or 0),
        input_tokens=r.input_tokens,
        output_tokens=r.output_tokens,
        events=r.events or [],
        created_at=r.created_at,
        started_at=r.started_at,
        finished_at=r.finished_at,
        duration_s=duration,
    )


def _active(r: Run) -> ActiveRun:
    setup = setup_service.setup_state(r)
    return ActiveRun(
        id=r.id,
        kind=r.kind,
        status=r.status,
        events=r.events or [],
        created_at=r.created_at,
        setup=SetupState(**setup) if setup else None,
    )


def _change(c: Change) -> ChangeRead:
    return ChangeRead(
        id=c.id,
        run_id=c.run_id,
        record_type=c.record_type,
        record_id=c.record_id,
        op=c.op,
        before=c.before,
        after=c.after,
        thread_ids=[],
        created_at=c.created_at,
    )


@shell_router.get("/app-shell", response_model=AppShell)
async def app_shell(runtime: Literal["v1", "v2"] = "v1") -> AppShell:
    """The fixed <head> content (CSP, base CSS, bridge) every app iframe is wrapped in,
    and the palettes it knows (for the palette tiles)."""
    return AppShell(
        head=shell_head(runtime),
        palettes=[
            PaletteInfo(
                id=p.id,
                name=p.name,
                accent=p.accent,
                accent_ink=p.ink,
                accent_soft=p.soft,
                series=p.series_hex,
            )
            for p in PALETTES.values()
        ],
    )


@router.get("", response_model=list[WorkspaceSummary])
async def list_workspaces(session: SessionDep, user: CurrentUser):
    return [_summary(w) for w in await service.list_workspaces(session, user.id)]


@router.post("", response_model=WorkspaceSummary, status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceCreate, session: SessionDep, user: CurrentUser):
    return _summary(await service.create_workspace(session, user.id, body.prompt, body.name))


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
async def get_workspace(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    w = await service.get_workspace(session, user.id, workspace_id)
    active = await runs_service.active_run(session, w.id)
    has_snapshot = await session.scalar(
        select(exists(store.undoable_snapshots(w.id).subquery().select()))
    )
    return WorkspaceDetail(
        id=w.id,
        name=w.name,
        prompt=w.prompt,
        status=w.status,
        data_version=w.data_version,
        app_version=w.app_version,
        last_synced_at=w.last_synced_at,
        record_counts=service.record_counts(w),
        queries=list((w.config or {}).get("queries", [])),
        palette=valid_palette(w.palette),
        active_run=_active(active) if active else None,
        last_error=w.last_error,
        can_undo=bool(has_snapshot) and active is None,
        created_at=w.created_at,
    )


@router.patch("/{workspace_id}", response_model=WorkspaceSummary)
async def rename_workspace(
    workspace_id: uuid.UUID, body: WorkspaceRename, session: SessionDep, user: CurrentUser
):
    return _summary(await service.rename_workspace(session, user.id, workspace_id, body.name))


@router.post("/{workspace_id}/setup", response_model=ActiveRun)
async def update_setup(
    workspace_id: uuid.UUID, body: SetupUpdate, session: SessionDep, user: CurrentUser
):
    """The user's answers to the clarifying questions while the workspace is built."""
    run = await setup_service.update_setup(session, user.id, workspace_id, answers=body.answers)
    return _active(run)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    await service.delete_workspace(session, user.id, workspace_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{workspace_id}/app", response_model=AppDoc)
async def get_app(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    w = await service.get_workspace(session, user.id, workspace_id)
    return AppDoc(html=w.app_html, version=w.app_version, runtime=app_runtime(w.app_html))


@router.get("/{workspace_id}/data", response_model=DataDoc)
async def get_data(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    w = await service.get_workspace(session, user.id, workspace_id)
    return DataDoc(data=w.data or {}, version=w.data_version)


@router.get("/{workspace_id}/guide", response_model=GuideDoc)
async def get_guide(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    w = await service.get_workspace(session, user.id, workspace_id)
    return GuideDoc(guide=w.guide, queries=list((w.config or {}).get("queries", [])))


@router.get("/{workspace_id}/changes", response_model=list[ChangeRead])
async def list_changes(
    workspace_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    before: datetime | None = None,
):
    w = await service.get_workspace(session, user.id, workspace_id)
    changes = await runs_service.list_changes(session, w.id, limit, before)
    # Source thread ids come from the record's current _sources for the cited messages.
    out = []
    for c in changes:
        item = _change(c)
        rec = (w.data or {}).get(c.record_type, {}).get(c.record_id) or {}
        wanted = set(c.source_message_ids or [])
        tids = [s["thread_id"] for s in rec.get("_sources", []) if s["message_id"] in wanted]
        item.thread_ids = list(dict.fromkeys(tids))
        out.append(item)
    return out


@router.get("/{workspace_id}/runs", response_model=list[RunRead])
async def list_runs(
    workspace_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
):
    w = await service.get_workspace(session, user.id, workspace_id)
    return [_run(r) for r in await runs_service.list_runs(session, w.id, limit)]


@router.post("/{workspace_id}/messages", response_model=RunCreated, status_code=202)
async def post_message(
    workspace_id: uuid.UUID, body: MessageCreate, session: SessionDep, user: CurrentUser
):
    w = await service.get_workspace(session, user.id, workspace_id)
    service.require_gmail(user, "first")
    run = await runs_service.enqueue(session, w.id, RunKind.EDIT, {"text": body.text.strip()})
    return RunCreated(run_id=run.id)


@router.post("/{workspace_id}/sync", response_model=RunCreated, status_code=202)
async def sync_now(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    w = await service.get_workspace(session, user.id, workspace_id)
    service.require_gmail(user, "first")
    run = await runs_service.enqueue(session, w.id, RunKind.SYNC, conflict_if_active=False)
    return RunCreated(run_id=run.id)


@router.post("/{workspace_id}/undo", response_model=DataDoc)
async def undo(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    w = await store.undo(session, user.id, workspace_id)
    return DataDoc(data=w.data or {}, version=w.data_version)


@router.post("/{workspace_id}/rebuild", response_model=WorkspaceSummary)
async def rebuild(workspace_id: uuid.UUID, session: SessionDep, user: CurrentUser):
    return _summary(await service.rebuild_workspace(session, user.id, workspace_id))
