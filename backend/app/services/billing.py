"""Mirror Stripe customers into `billing_customers`, which the access rule reads.

A webhook event only tells us *which* customer changed. We then read that customer and
their subscriptions from Stripe and store the result, so events that arrive late, twice
or out of order still leave the row matching Stripe (no event log needed).

What is copied: the email (lowercased) and the best subscription (id, status, trial end).
Logs carry Stripe ids and counts only, never emails.
"""

import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.stripe_api import StripeClient
from app.models.access import BillingCustomer

logger = logging.getLogger(__name__)

# A customer can have several subscriptions; the one that gives the most access counts.
_RANK = {"active": 0, "trialing": 1, "past_due": 2}

# Events that can change who has access. Anything else is acknowledged and ignored.
CUSTOMER_EVENTS = {"customer.created", "customer.updated", "customer.deleted"}
OBJECT_EVENTS = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.paused",
    "customer.subscription.resumed",
}


def best_subscription(subscriptions: list[dict[str, Any]]) -> dict[str, Any] | None:
    live = [s for s in subscriptions if s.get("status") in _RANK]
    if live:
        return min(live, key=lambda s: _RANK[s["status"]])
    return max(subscriptions, key=lambda s: s.get("created") or 0, default=None)


def _timestamp(value: Any) -> datetime | None:
    """A Stripe Unix timestamp (seconds) as an aware datetime."""
    try:
        return datetime.fromtimestamp(int(value), UTC) if value else None
    except (TypeError, ValueError, OverflowError):
        return None


def _id(value: Any) -> str | None:
    """A Stripe reference: an id string, or an expanded object with an id."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        return value.get("id")
    return None


def event_customer_id(event: dict[str, Any]) -> str | None:
    obj = (event.get("data") or {}).get("object") or {}
    kind = event.get("type")
    if kind in CUSTOMER_EVENTS:
        return _id(obj.get("id"))
    if kind in OBJECT_EVENTS:
        return _id(obj.get("customer"))
    return None


async def _row(session: AsyncSession, customer_id: str) -> BillingCustomer | None:
    return await session.scalar(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == customer_id)
    )


async def store(
    session: AsyncSession, customer: dict[str, Any], subscriptions: list[dict[str, Any]]
) -> BillingCustomer:
    row = await _row(session, customer["id"])
    if row is None:
        row = BillingCustomer(stripe_customer_id=customer["id"])
        session.add(row)
    best = best_subscription(subscriptions)
    row.email = (customer.get("email") or "").strip().lower()
    row.subscription_id = best["id"] if best else None
    row.subscription_status = best.get("status") if best else None
    row.trial_ends_at = _timestamp(best.get("trial_end")) if best else None
    row.deleted = False
    await session.flush()
    return row


async def mark_deleted(session: AsyncSession, customer_id: str) -> BillingCustomer | None:
    row = await _row(session, customer_id)
    if row is not None and not row.deleted:
        row.deleted = True
        await session.flush()
    return row


async def sync_customer(
    session: AsyncSession, stripe: StripeClient, customer_id: str
) -> BillingCustomer | None:
    data = await stripe.customer(customer_id)
    if data is None or data.get("deleted"):
        return await mark_deleted(session, customer_id)
    return await store(session, data, await stripe.subscriptions(customer_id))


async def sync_email(session: AsyncSession, stripe: StripeClient, email: str) -> int:
    """Refresh every customer Stripe has for this (lowercased) email. Returns how many."""
    seen: set[str] = set()
    async for c in stripe.customers(email=email):
        await store(session, c, await stripe.subscriptions(c["id"]))
        seen.add(c["id"])
    # Known here under this email but not listed by Stripe: deleted, or the email changed.
    stale = select(BillingCustomer.stripe_customer_id).where(
        BillingCustomer.email == email, BillingCustomer.deleted.is_(False)
    )
    if seen:
        stale = stale.where(BillingCustomer.stripe_customer_id.not_in(seen))
    for customer_id in list(await session.scalars(stale)):
        await sync_customer(session, stripe, customer_id)
    return len(seen)


async def sync_all(session: AsyncSession, stripe: StripeClient) -> int:
    """Reconcile with Stripe: every live customer, and mark the rest deleted."""
    by_customer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for s in await stripe.subscriptions():
        if cid := _id(s.get("customer")):
            by_customer[cid].append(s)
    seen: set[str] = set()
    async for c in stripe.customers():
        await store(session, c, by_customer.get(c["id"], []))
        seen.add(c["id"])
    gone = update(BillingCustomer).where(BillingCustomer.deleted.is_(False))
    if seen:
        gone = gone.where(BillingCustomer.stripe_customer_id.not_in(seen))
    await session.execute(gone.values(deleted=True))
    await session.flush()
    logger.info("stripe sync: %s customers", len(seen))
    return len(seen)


async def handle_event(
    session: AsyncSession, stripe: StripeClient, event: dict[str, Any]
) -> str | None:
    """Apply one verified webhook event. Returns the customer id it touched, if any."""
    customer_id = event_customer_id(event)
    if customer_id is None:
        return None
    if event.get("type") == "customer.deleted":
        await mark_deleted(session, customer_id)
    else:
        await sync_customer(session, stripe, customer_id)
    logger.info("stripe event %s: customer=%s", event.get("type"), customer_id)
    return customer_id
