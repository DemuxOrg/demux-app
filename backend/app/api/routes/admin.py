"""`/api/v1/admin`: usage, costs, the demo inbox and agent evals, for Demux staff only.

Every route depends on `get_admin_user` (router level): 401 without a session, the same
404 as an unknown URL for anyone who is not an admin, and one `admin_audit` row per
request. Response shapes are in `app/schemas/admin.py` (privacy rules there).
"""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AdminUser, SessionDep, get_admin_user
from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.schemas.admin import (
    AdminOverview,
    AdminUserDetail,
    AdminUserRow,
    AdminWorkspace,
    AdminWorkspaceDetail,
    DailyCount,
    DailyFailures,
    DailyKeyCost,
    DailyTokens,
    DailyUserCost,
    DailyWorkspaceUsage,
    DemoCleanup,
    DemoInboxState,
    DemoSeedCreate,
    DemoSeedRead,
    EvalAsk,
    EvalCheck,
    EvalClarify,
    EvalGroup,
    EvalParts,
    EvalQuestion,
    EvalRetrieval,
    EvalRunCreate,
    EvalRunDetail,
    EvalRunRow,
    EvalScenarioInfo,
    EvalScenarioResult,
    EvalsState,
    EvalStep,
)
from app.services import admin as service
from app.services import demo, evals

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_admin_user)])


def _days(days: int) -> int:
    if days not in service.RANGES:
        raise ValidationError(f"days must be one of {', '.join(map(str, service.RANGES))}.")
    return days


@router.get("/overview", response_model=AdminOverview)
async def overview(session: SessionDep, days: int = Query(30)) -> AdminOverview:
    o = await service.overview(session, _days(days))
    return AdminOverview(
        days=o.days,
        start=o.start,
        end=o.end,
        active_users=o.active_users,
        total_users=o.total_users,
        workspaces=o.workspaces,
        new_workspaces=o.new_workspaces,
        builds=o.builds,
        syncs=o.syncs,
        edits=o.edits,
        input_tokens=o.input_tokens,
        output_tokens=o.output_tokens,
        cost_usd=o.cost_usd,
        failed_runs=o.failed_runs,
        finished_runs=o.finished_runs,
        cost_by_phase=[DailyKeyCost(date=d, key=k, cost_usd=c) for d, k, c in o.cost_by_phase],
        cost_by_model=[DailyKeyCost(date=d, key=k, cost_usd=c) for d, k, c in o.cost_by_model],
        tokens=[DailyTokens(date=d, input_tokens=i, output_tokens=x) for d, i, x in o.tokens],
        cost_per_user=[
            DailyUserCost(date=d, active_users=n, p50_usd=p50, p95_usd=p95)
            for d, n, p50, p95 in o.cost_per_user
        ],
        failures=[DailyFailures(date=d, finished=f, failed=x) for d, f, x in o.failures],
    )


@router.get("/users", response_model=list[AdminUserRow])
async def users(session: SessionDep) -> list[AdminUserRow]:
    return [AdminUserRow.model_validate(r) for r in await service.users_table(session)]


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def user_detail(user_id: uuid.UUID, session: SessionDep) -> AdminUserDetail:
    d = await service.user_detail(session, user_id)
    if d is None:
        raise NotFoundError("User not found.")
    return AdminUserDetail(
        user=AdminUserRow.model_validate(d.user),
        mailbox_daily=[DailyCount(date=day, count=n) for day, n in d.mailbox_daily],
        workspaces=[AdminWorkspace.model_validate(w) for w in d.workspaces],
    )


@router.get("/workspaces/{workspace_id}", response_model=AdminWorkspaceDetail)
async def workspace_detail(
    workspace_id: uuid.UUID, session: SessionDep, days: int = Query(30)
) -> AdminWorkspaceDetail:
    d = await service.workspace_detail(session, workspace_id, _days(days))
    if d is None:
        raise NotFoundError("Workspace not found.")
    return AdminWorkspaceDetail(
        workspace=AdminWorkspace.model_validate(d.workspace),
        owner_email=d.owner_email,
        days=d.days,
        daily=[
            DailyWorkspaceUsage(date=day, cost_usd=c, input_tokens=i, output_tokens=o, emails=e)
            for day, c, i, o, e in d.daily
        ],
    )


@router.get("/demo", response_model=DemoInboxState)
async def demo_state(session: SessionDep) -> DemoInboxState:
    return DemoInboxState(
        configured=settings.demo_inbox_configured,
        inbox_email=settings.TEST_GMAIL or None,
        model=settings.DEMO_MODEL or settings.BUILD_MODEL,
        seeds=[DemoSeedRead.model_validate(s) for s in await demo.list_seeds(session)],
    )


@router.post("/demo/seeds", response_model=DemoSeedRead, status_code=status.HTTP_202_ACCEPTED)
async def create_seed(body: DemoSeedCreate, admin: AdminUser, session: SessionDep) -> DemoSeedRead:
    seed = await demo.create_seed(session, admin, body.prompt, body.thread_count)
    await session.refresh(seed)
    return DemoSeedRead.model_validate(seed)


@router.post("/demo/cleanup", response_model=DemoCleanup)
async def cleanup() -> DemoCleanup:
    return DemoCleanup(removed=await demo.remove_demo_threads())


# ------------------------------------------------------------------ evals


def _pct(v: Any) -> float | None:
    return None if v is None else round(100 * float(v), 1)


def _spec(spec: dict[str, Any]) -> str:
    """A check as written: `value {"find": [...], "any_of": [...]}` (kind first)."""
    rest = {k: v for k, v in spec.items() if k != "kind"}
    return f"{spec.get('kind', '?')} {json.dumps(rest, ensure_ascii=False)}"


def _scenario(r: dict[str, Any]) -> EvalScenarioResult:
    """One scenario of a stored report (eval/agent/runner.py) as the API shape."""
    ret = r.get("retrieval")
    clar = r.get("clarify")
    return EvalScenarioResult(
        id=r["id"],
        repeat=r.get("repeat", 1),
        prompt=r.get("prompt", ""),
        score=_pct(r["score"]) or 0.0,
        parts=EvalParts(**{k: _pct(v) for k, v in (r.get("parts") or {}).items()}),
        retrieval=EvalRetrieval(**{**ret, "groups": [EvalGroup(**g) for g in ret["groups"]]})
        if ret
        else None,
        asks=[EvalAsk(**a) for a in r.get("asks") or []],
        clarify=EvalClarify(**{**clar, "questions": [EvalQuestion(**q) for q in clar["questions"]]})
        if clar
        else None,
        steps=[
            EvalStep(
                name=st["name"],
                kind=st["kind"],
                error=st.get("error"),
                cost_usd=st["cost_usd"],
                input_tokens=st["input_tokens"],
                output_tokens=st["output_tokens"],
                latency_s=st["latency_s"],
                record_count=st["records"],
                app_renders=st["app_renders"],
                checks=[
                    EvalCheck(
                        step=c["step"],
                        kind=c["kind"],
                        passed=c["passed"],
                        expected=_spec(c["spec"]),
                        detail=c.get("detail", ""),
                    )
                    for c in st.get("checks") or []
                ],
            )
            for st in r.get("steps") or []
        ],
    )


@router.get("/evals", response_model=EvalsState)
async def evals_state(session: SessionDep) -> EvalsState:
    return EvalsState(
        build_model=settings.BUILD_MODEL,
        scenarios=[EvalScenarioInfo(**s) for s in evals.scenarios()],
        runs=[EvalRunRow.model_validate(r) for r in await evals.list_evals(session)],
    )


@router.post("/evals", response_model=EvalRunRow, status_code=status.HTTP_202_ACCEPTED)
async def create_eval(body: EvalRunCreate, admin: AdminUser, session: SessionDep) -> EvalRunRow:
    run = await evals.create_eval(session, admin, body.repeats, body.scenario_ids)
    await session.refresh(run)
    return EvalRunRow.model_validate(run)


@router.get("/evals/{eval_id}", response_model=EvalRunDetail)
async def eval_detail(eval_id: uuid.UUID, session: SessionDep) -> EvalRunDetail:
    run = await evals.get_eval(session, eval_id)
    row = EvalRunRow.model_validate(run)
    results = (run.report or {}).get("results") or []
    return EvalRunDetail(**row.model_dump(), scenarios=[_scenario(r) for r in results])


@router.post("/evals/{eval_id}/cancel", response_model=EvalRunRow)
async def cancel_eval(eval_id: uuid.UUID, session: SessionDep) -> EvalRunRow:
    run = await evals.cancel_eval(session, eval_id)
    await session.refresh(run)
    return EvalRunRow.model_validate(run)
