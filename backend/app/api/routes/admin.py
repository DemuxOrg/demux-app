"""`/api/v1/admin`: usage, costs, the demo inbox and access (free-access grants, Stripe
customers), for Demux staff only.

Every route depends on `get_admin_user` (router level): 401 without a session, the same
404 as an unknown URL for anyone who is not an admin, and one `admin_audit` row per
request. Response shapes are in `app/schemas/admin.py` (privacy rules there).
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import AdminUser, SessionDep, StripeDep, get_admin_user
from app.api.routes.billing import StripeUnavailableError
from app.billing.stripe_api import StripeError
from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.schemas.admin import (
    AdminAccessState,
    AdminCustomer,
    AdminGrant,
    AdminGrantCreate,
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
    StripeSync,
)
from app.services import access, billing, demo
from app.services import admin as service

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


@router.get("/access", response_model=AdminAccessState)
async def access_state(session: SessionDep) -> AdminAccessState:
    grants, customers = await service.access_overview(session)
    return AdminAccessState(
        stripe_configured=bool(settings.STRIPE_SECRET_KEY),
        webhook_configured=bool(settings.STRIPE_WEBHOOK_SECRET),
        grants=[AdminGrant.model_validate(g) for g in grants],
        customers=[AdminCustomer.model_validate(c) for c in customers],
    )


@router.post("/access/grants", response_model=AdminGrant, status_code=status.HTTP_201_CREATED)
async def create_grant(body: AdminGrantCreate, admin: AdminUser, session: SessionDep) -> AdminGrant:
    """Give an email free access (or renew it). They sign up with that email."""
    expires_at = body.expires_at
    if expires_at is not None:
        expires_at = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            raise ValidationError("The end date must be in the future.")
    g = await access.grant(session, admin, body.email, body.note, expires_at)
    return AdminGrant.model_validate((await service.grant_rows(session, [g]))[0])


@router.post("/access/grants/{grant_id}/revoke", response_model=AdminGrant)
async def revoke_grant(grant_id: uuid.UUID, session: SessionDep) -> AdminGrant:
    g = await access.revoke(session, grant_id)
    if g is None:
        raise NotFoundError("Grant not found.")
    return AdminGrant.model_validate((await service.grant_rows(session, [g]))[0])


@router.post("/access/stripe-sync", response_model=StripeSync)
async def stripe_sync(session: SessionDep, stripe: StripeDep) -> StripeSync:
    """Re-read every Stripe customer (first deploy, or after a webhook outage)."""
    if stripe is None:
        raise ValidationError("Stripe is not configured: set STRIPE_SECRET_KEY.")
    try:
        return StripeSync(synced=await billing.sync_all(session, stripe))
    except StripeError as e:
        raise StripeUnavailableError(f"Could not read Stripe: {e}") from e
