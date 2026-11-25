"""Who may use Demux: one rule for sign-up, every app request, the worker and /admin.

Demux is for paying customers. A login email has access when one of these holds:

1. **Admin**: listed in ADMIN_EMAILS, or `users.is_admin` (Demux staff).
2. **Subscription**: a Stripe customer with this email has a subscription that is
   `active` or `past_due` (Stripe is still retrying a failed payment).
3. **Trial**: that subscription is `trialing`: the 14-day free trial the landing page's
   checkout starts. Stripe charges €12 when it ends (then `active`), or the customer
   cancels.
4. **Free access**: an admin gave this email access in /admin/access (beta users,
   friends), not revoked and not expired.

Sign-up is refused unless the email has access (`signup_check`), so an account can only
be created by someone who paid, was invited, or is staff, and `users.email` being unique
means one account per email. Access is checked again on every app request
(`get_entitled_user`) and before each scheduled sync, so a lapsed subscription stops
LLM spend at once. Nothing is deleted: the workspaces come back when they subscribe.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.stripe_api import StripeClient
from app.core.config import settings
from app.models.access import AccessGrant, BillingCustomer
from app.models.user import User
from app.services import billing

PAID = ("active", "past_due")
TRIALING = "trialing"


class AccessStatus(StrEnum):
    ADMIN = "admin"
    SUBSCRIPTION = "subscription"
    GRANT = "grant"
    TRIAL = "trial"
    NONE = "none"


@dataclass(frozen=True)
class Access:
    status: AccessStatus
    ends_at: datetime | None = None  # TRIAL: first charge; GRANT: expiry (None: open-ended)
    subscribe_url: str | None = None  # NONE: where to start a trial

    @property
    def allowed(self) -> bool:
        return self.status != AccessStatus.NONE


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_admin_email(email: str) -> bool:
    return normalize_email(email) in settings.admin_emails


def grant_active(g: AccessGrant, now: datetime) -> bool:
    return g.revoked_at is None and (g.expires_at is None or g.expires_at > now)


def customer_access(c: BillingCustomer) -> AccessStatus:
    """What one Stripe customer gives: SUBSCRIPTION, TRIAL or NONE."""
    if c.deleted:
        return AccessStatus.NONE
    if c.subscription_status in PAID:
        return AccessStatus.SUBSCRIPTION
    if c.subscription_status == TRIALING:
        return AccessStatus.TRIAL
    return AccessStatus.NONE


def subscribe_url() -> str:
    """The landing page's pricing card: a new checkout with a 14-day free trial."""
    return f"{settings.LANDING_URL.rstrip('/')}/#pricing"


def decide(
    *,
    admin: bool,
    grants: Iterable[AccessGrant],
    customers: Iterable[BillingCustomer],
    now: datetime,
) -> Access:
    """The rule, on rows already loaded for one email. Pure: no I/O."""
    if admin:
        return Access(AccessStatus.ADMIN)
    customers = list(customers)
    if any(customer_access(c) == AccessStatus.SUBSCRIPTION for c in customers):
        return Access(AccessStatus.SUBSCRIPTION)
    trials = [c for c in customers if customer_access(c) == AccessStatus.TRIAL]
    if trials:
        ends = [c.trial_ends_at for c in trials if c.trial_ends_at]
        return Access(AccessStatus.TRIAL, ends_at=max(ends) if ends else None)
    active = [g for g in grants if grant_active(g, now)]
    if active:
        open_ended = [g for g in active if g.expires_at is None]
        ends = None if open_ended else max(g.expires_at for g in active if g.expires_at)
        return Access(AccessStatus.GRANT, ends_at=ends)
    return Access(AccessStatus.NONE, subscribe_url=subscribe_url())


async def _rows(
    session: AsyncSession, emails: set[str]
) -> tuple[dict[str, list[AccessGrant]], dict[str, list[BillingCustomer]]]:
    grants: dict[str, list[AccessGrant]] = defaultdict(list)
    customers: dict[str, list[BillingCustomer]] = defaultdict(list)
    if not emails:
        return grants, customers
    for g in await session.scalars(select(AccessGrant).where(AccessGrant.email.in_(emails))):
        grants[g.email].append(g)
    for c in await session.scalars(
        select(BillingCustomer).where(BillingCustomer.email.in_(emails))
    ):
        customers[c.email].append(c)
    return grants, customers


async def for_email(
    session: AsyncSession, email: str, *, admin: bool = False, now: datetime | None = None
) -> Access:
    email = normalize_email(email)
    grants, customers = await _rows(session, {email})
    return decide(
        admin=admin or is_admin_email(email),
        grants=grants[email],
        customers=customers[email],
        now=now or datetime.now(UTC),
    )


async def for_user(session: AsyncSession, user: User, *, now: datetime | None = None) -> Access:
    return await for_email(session, user.email, admin=user.is_admin, now=now)


async def for_users(
    session: AsyncSession, users: Iterable[User], *, now: datetime | None = None
) -> dict[uuid.UUID, Access]:
    """Access of many users in two queries (admin users table, the sync scheduler)."""
    users = list(users)
    grants, customers = await _rows(session, {normalize_email(u.email) for u in users})
    now = now or datetime.now(UTC)
    out = {}
    for u in users:
        email = normalize_email(u.email)
        out[u.id] = decide(
            admin=u.is_admin or is_admin_email(email),
            grants=grants[email],
            customers=customers[email],
            now=now,
        )
    return out


async def users_with_access(session: AsyncSession, user_ids: Iterable[uuid.UUID]) -> set[uuid.UUID]:
    ids = set(user_ids)
    if not ids:
        return set()
    users = await session.scalars(select(User).where(User.id.in_(ids)))
    return {uid for uid, a in (await for_users(session, users)).items() if a.allowed}


async def signup_check(session: AsyncSession, email: str, stripe: StripeClient | None) -> Access:
    """May this email create an account? Asked by the frontend before better-auth does.

    Known customers are answered from the database. Anyone else is looked up in Stripe
    once (the webhook may be a few seconds behind a fresh checkout, or was missed).
    """
    access = await for_email(session, email)
    if access.allowed or stripe is None:
        return access
    await billing.sync_email(session, stripe, normalize_email(email))
    return await for_email(session, email)


# ------------------------------------------------------------------ free access (admin)


async def list_grants(session: AsyncSession) -> list[AccessGrant]:
    return list(await session.scalars(select(AccessGrant).order_by(AccessGrant.created_at.desc())))


async def grant(
    session: AsyncSession,
    admin: User,
    email: str,
    note: str = "",
    expires_at: datetime | None = None,
) -> AccessGrant:
    """Give an email free access. Granting an email again renews it (and un-revokes it)."""
    email = normalize_email(email)
    g = await session.scalar(select(AccessGrant).where(AccessGrant.email == email))
    if g is None:
        g = AccessGrant(email=email)
        session.add(g)
    g.note = note.strip()
    g.expires_at = expires_at
    g.revoked_at = None
    g.created_by = admin.id
    await session.flush()
    await session.refresh(g)
    return g


async def revoke(session: AsyncSession, grant_id: uuid.UUID) -> AccessGrant | None:
    g = await session.get(AccessGrant, grant_id)
    if g is None:
        return None
    if g.revoked_at is None:
        g.revoked_at = datetime.now(UTC)
        await session.flush()
        await session.refresh(g)
    return g
