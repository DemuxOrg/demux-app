"""Access: the rule (who may use Demux), the sign-up check, the app gate, the Stripe
webhook and sync, free-access grants in /admin, and the sync scheduler.

Stripe is replaced by `FakeStripe` (no network); webhook requests are signed for real.
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import func, select

from app.api.deps import get_stripe
from app.billing.stripe_api import SignatureError, StripeError, verify_webhook
from app.core.config import settings
from app.main import app
from app.models import AccessGrant, BillingCustomer, Workspace, WorkspaceStatus
from app.services import access, runs
from app.services.access import AccessStatus

WHSEC = "whsec_test_secret"
INTERNAL = "internal-test-secret"
WEBHOOK = "/api/v1/billing/stripe/webhook"
CHECK = "/api/v1/internal/signup-check"
LANDING = "https://www.usedemux.com"


class FakeStripe:
    """Stands in for StripeClient: customers and subscriptions kept in memory."""

    def __init__(self) -> None:
        self.by_id: dict[str, dict[str, Any]] = {}
        self.subs: list[dict[str, Any]] = []
        self.down = False

    def add(self, customer: dict[str, Any], *subs: dict[str, Any]) -> None:
        self.by_id[customer["id"]] = customer
        self.subs += subs

    def _check(self) -> None:
        if self.down:
            raise StripeError("Stripe unreachable (ConnectError)")

    async def customer(self, customer_id: str) -> dict[str, Any] | None:
        self._check()
        return self.by_id.get(customer_id)

    async def customers(self, email: str | None = None):
        self._check()
        for c in list(self.by_id.values()):
            if not c.get("deleted") and (email is None or c.get("email") == email):
                yield c

    async def subscriptions(self, customer_id: str | None = None) -> list[dict[str, Any]]:
        self._check()
        return [s for s in self.subs if customer_id in (None, s["customer"])]


def customer(cid: str, email: str, **metadata: str) -> dict[str, Any]:
    return {"id": cid, "object": "customer", "email": email, "metadata": metadata}


def sub(sid: str, cid: str, status: str, created: int = 1, **extra: Any) -> dict[str, Any]:
    return {
        "id": sid,
        "object": "subscription",
        "customer": cid,
        "status": status,
        "created": created,
        **extra,
    }


def trialing(sid: str, cid: str, days_left: int = 14) -> dict[str, Any]:
    """A subscription as the landing page's checkout starts it: a 14-day free trial."""
    trial_end = int((datetime.now(UTC) + timedelta(days=days_left)).timestamp())
    return sub(sid, cid, "trialing", trial_end=trial_end)


def event(kind: str, obj: dict[str, Any]) -> dict[str, Any]:
    return {"id": f"evt_{uuid.uuid4().hex[:8]}", "type": kind, "data": {"object": obj}}


def signed(payload: dict[str, Any], secret: str = WHSEC, at: int | None = None):
    body = json.dumps(payload).encode()
    t = at if at is not None else int(time.time())
    sig = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return body, {"stripe-signature": f"t={t},v1={sig}", "content-type": "application/json"}


@pytest.fixture
def stripe(monkeypatch) -> FakeStripe:
    fake = FakeStripe()
    app.dependency_overrides[get_stripe] = lambda: fake
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", WHSEC)
    monkeypatch.setattr(settings, "INTERNAL_API_SECRET", INTERNAL)
    monkeypatch.setattr(settings, "LANDING_URL", LANDING)
    return fake


@pytest.fixture
def admin(monkeypatch):
    """The dev user (the `client` fixture) is an admin."""
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "dev@demux.local")


async def post_event(client, kind: str, obj: dict[str, Any]):
    body, headers = signed(event(kind, obj))
    return await client.post(WEBHOOK, content=body, headers=headers)


async def verdict(client, email: str) -> dict[str, Any]:
    r = await client.post(
        CHECK, json={"email": email}, headers={"authorization": f"Bearer {INTERNAL}"}
    )
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ the rule


NOW = datetime(2027, 8, 5, 12, 0, tzinfo=UTC)


def _decide(*, admin=False, grants=(), customers=()):
    return access.decide(admin=admin, grants=grants, customers=customers, now=NOW)


def _customer(**kw) -> BillingCustomer:
    return BillingCustomer(stripe_customer_id=kw.pop("cid", "cus_1"), email="a@x.example", **kw)


def test_admins_always_have_access():
    assert _decide(admin=True).status == AccessStatus.ADMIN


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("active", AccessStatus.SUBSCRIPTION),
        ("trialing", AccessStatus.TRIAL),  # the 14-day free trial
        ("past_due", AccessStatus.SUBSCRIPTION),  # Stripe is still retrying the payment
        ("canceled", AccessStatus.NONE),
        ("unpaid", AccessStatus.NONE),
        ("incomplete_expired", AccessStatus.NONE),
        ("paused", AccessStatus.NONE),
    ],
)
def test_subscription_statuses(status, expected):
    assert _decide(customers=[_customer(subscription_status=status)]).status == expected


def test_a_deleted_customer_gives_nothing():
    c = _customer(subscription_status="active", deleted=True)
    assert _decide(customers=[c]).status == AccessStatus.NONE


def test_a_trial_shows_when_the_first_charge_is():
    ends = NOW + timedelta(days=9)
    a = _decide(customers=[_customer(subscription_status="trialing", trial_ends_at=ends)])
    assert a == access.Access(AccessStatus.TRIAL, ends_at=ends)


def test_no_subscription_means_no_access_and_a_link_to_start_a_trial():
    for c in (_customer(), _customer(subscription_status="canceled")):
        a = _decide(customers=[c])
        assert a.status == AccessStatus.NONE and a.subscribe_url == f"{LANDING}/#pricing"


def test_grants():
    forever = AccessGrant(email="a@x.example")
    later = AccessGrant(email="a@x.example", expires_at=NOW + timedelta(days=3))
    assert _decide(grants=[forever]) == access.Access(AccessStatus.GRANT)
    assert _decide(grants=[later]).ends_at == NOW + timedelta(days=3)
    assert _decide(grants=[forever, later]).ends_at is None
    revoked = AccessGrant(email="a@x.example", revoked_at=NOW - timedelta(hours=1))
    expired = AccessGrant(email="a@x.example", expires_at=NOW - timedelta(seconds=1))
    assert _decide(grants=[revoked]).status == AccessStatus.NONE
    assert _decide(grants=[expired]).status == AccessStatus.NONE


def test_best_access_wins():
    paid = _customer(subscription_status="active")
    trial = _customer(cid="cus_2", subscription_status="trialing")
    old = _customer(cid="cus_3", subscription_status="canceled")
    grant = AccessGrant(email="a@x.example")
    assert _decide(grants=[grant], customers=[old, trial, paid]).status == AccessStatus.SUBSCRIPTION
    assert _decide(grants=[grant], customers=[old, trial]).status == AccessStatus.TRIAL
    assert _decide(grants=[grant], customers=[old]).status == AccessStatus.GRANT


# ------------------------------------------------------------------ webhook signature


def test_verify_webhook():
    body, headers = signed({"id": "evt_1", "type": "x"})
    header = headers["stripe-signature"]
    assert verify_webhook(body, header, WHSEC)["id"] == "evt_1"
    # While a secret is rolled, Stripe sends one v1 per secret.
    _, other = signed({"id": "evt_1", "type": "x"}, secret="whsec_old")
    rolled = f"{header},v1={other['stripe-signature'].split('v1=')[1]}"
    assert verify_webhook(body, rolled, WHSEC)["id"] == "evt_1"
    bad = [
        (body, header, "whsec_wrong"),
        (body + b" ", header, WHSEC),
        (body, None, WHSEC),
        (body, "v1=abc", WHSEC),
        (body, "t=notanumber,v1=abc", WHSEC),
    ]
    for payload, h, secret in bad:
        with pytest.raises(SignatureError):
            verify_webhook(payload, h, secret)
    old_body, old = signed({"id": "evt_1"}, at=int(time.time()) - 600)
    with pytest.raises(SignatureError):
        verify_webhook(old_body, old["stripe-signature"], WHSEC)


# ------------------------------------------------------------------ webhook endpoint


async def test_webhook_rejects_unsigned_requests(client, session, stripe):
    stripe.add(customer("cus_1", "payer@x.example"), sub("sub_1", "cus_1", "active"))
    obj = {"id": "cus_1"}
    body, headers = signed(event("customer.updated", obj), secret="whsec_attacker")
    r = await client.post(WEBHOOK, content=body, headers=headers)
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_signature"
    r = await client.post(WEBHOOK, content=body, headers={"content-type": "application/json"})
    assert r.status_code == 400
    assert await session.scalar(select(func.count()).select_from(BillingCustomer)) == 0


async def test_webhook_needs_configuration(client, stripe, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    assert (await post_event(client, "customer.updated", {"id": "cus_1"})).status_code == 503


async def test_trial_then_paid_then_canceled(client, session, stripe):
    email = "founder@x.example"
    stripe.add(customer("cus_1", "Founder@X.example"), trialing("sub_1", "cus_1"))

    r = await post_event(
        client,
        "checkout.session.completed",
        {"id": "cs_test_1", "customer": "cus_1", "subscription": "sub_1", "mode": "subscription"},
    )
    assert r.status_code == 200 and r.json() == {"received": True}
    row = await session.scalar(select(BillingCustomer))
    assert (row.email, row.subscription_status) == (email, "trialing")
    a = await access.for_email(session, email)
    assert a.status == AccessStatus.TRIAL
    assert a.ends_at == datetime.fromtimestamp(stripe.subs[0]["trial_end"], UTC)

    # Day 14: Stripe charges the card.
    stripe.subs[0]["status"] = "active"
    await post_event(client, "customer.subscription.updated", {"id": "sub_1", "customer": "cus_1"})
    assert (await access.for_email(session, email)).status == AccessStatus.SUBSCRIPTION

    # ...and later they cancel in the customer portal.
    stripe.subs[0]["status"] = "canceled"
    await post_event(client, "customer.subscription.deleted", {"id": "sub_1", "customer": "cus_1"})
    a = await access.for_email(session, email)
    assert a.status == AccessStatus.NONE and a.subscribe_url == f"{LANDING}/#pricing"

    stripe.by_id["cus_1"] = {"id": "cus_1", "deleted": True}
    await post_event(client, "customer.deleted", {"id": "cus_1"})
    await session.refresh(row)
    assert row.deleted is True


async def test_webhook_events_are_idempotent_and_order_free(client, session, stripe):
    stripe.add(customer("cus_1", "payer@x.example"), sub("sub_1", "cus_1", "active"))
    # Out of order: the "created" event arrives after "updated", twice.
    for kind in (
        "customer.subscription.updated",
        "customer.subscription.created",
        "customer.subscription.created",
    ):
        r = await post_event(client, kind, {"id": "sub_1", "customer": "cus_1"})
        assert r.status_code == 200
    rows = list(await session.scalars(select(BillingCustomer)))
    assert [(r.stripe_customer_id, r.subscription_status) for r in rows] == [("cus_1", "active")]


async def test_webhook_ignores_other_events(client, session, stripe):
    r = await post_event(client, "invoice.paid", {"id": "in_1", "customer": "cus_1"})
    assert r.status_code == 200
    assert await session.scalar(select(func.count()).select_from(BillingCustomer)) == 0


async def test_webhook_asks_stripe_to_retry_when_it_is_down(client, stripe):
    stripe.down = True
    r = await post_event(client, "customer.updated", {"id": "cus_1"})
    assert r.status_code == 502


# ------------------------------------------------------------------ sign-up check


async def test_signup_check_is_server_to_server_only(client, stripe, monkeypatch):
    r = await client.post(CHECK, json={"email": "a@x.example"})
    assert r.status_code == 401
    r = await client.post(
        CHECK, json={"email": "a@x.example"}, headers={"authorization": "Bearer nope"}
    )
    assert r.status_code == 401
    monkeypatch.setattr(settings, "INTERNAL_API_SECRET", "")
    r = await client.post(
        CHECK, json={"email": "a@x.example"}, headers={"authorization": "Bearer "}
    )
    assert r.status_code == 503
    assert CHECK not in app.openapi()["paths"] and WEBHOOK not in app.openapi()["paths"]


async def test_signup_is_refused_without_access(client, stripe):
    assert await verdict(client, "stranger@x.example") == {"allowed": False}


async def test_signup_for_admins_and_free_access(client, session, stripe, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", "Boss@X.example, other@x.example")
    assert (await verdict(client, "boss@x.example"))["allowed"] is True
    session.add_all(
        [
            AccessGrant(email="friend@x.example", note="Beta tester"),
            AccessGrant(email="gone@x.example", expires_at=datetime.now(UTC) - timedelta(days=1)),
        ]
    )
    await session.flush()
    assert (await verdict(client, "Friend@X.example"))["allowed"] is True
    assert (await verdict(client, "gone@x.example"))["allowed"] is False


async def test_signup_finds_a_fresh_stripe_customer(client, session, stripe):
    """The webhook has not arrived yet (or was missed): Stripe is asked directly."""
    stripe.add(customer("cus_9", "payer@x.example"), sub("sub_9", "cus_9", "active"))
    assert (await verdict(client, "payer@x.example"))["allowed"] is True
    row = await session.scalar(
        select(BillingCustomer).where(BillingCustomer.stripe_customer_id == "cus_9")
    )
    assert row is not None and row.subscription_status == "active"


async def test_signup_right_after_starting_a_trial(client, stripe):
    """The webhook may not have arrived yet: Stripe is asked and the trial counts."""
    stripe.add(customer("cus_1", "new@x.example"), trialing("sub_1", "cus_1"))
    assert await verdict(client, "new@x.example") == {"allowed": True}


async def test_signup_fails_closed_when_stripe_is_down(client, stripe):
    stripe.down = True
    assert (await verdict(client, "payer@x.example"))["allowed"] is False


# ------------------------------------------------------------------ the app gate


async def test_every_workspace_route_is_402_without_access(client, no_access):
    me = (await client.get("/api/v1/me")).json()
    assert me["access"]["status"] == "none" and me["access"]["subscribe_url"]
    paths = [
        (method.upper(), path.replace("{workspace_id}", str(uuid.uuid4())))
        for path, ops in app.openapi()["paths"].items()
        if path.startswith("/api/v1/workspaces")
        for method in ops
    ]
    assert len(paths) >= 10
    for method, path in paths:
        r = await client.request(method, path, json={})
        assert r.status_code == 402, (method, path, r.text)
        assert r.json()["error"]["code"] == "subscription_required"


async def test_refresh_reads_stripe_after_subscribing(client, no_access, stripe):
    stripe.add(customer("cus_1", "dev@demux.local"), sub("sub_1", "cus_1", "active"))
    me = (await client.post("/api/v1/me/access/refresh")).json()
    assert me["access"]["status"] == "subscription"
    assert (await client.get("/api/v1/workspaces")).status_code == 200


async def test_syncs_pause_for_users_without_access(session, dev_user, no_access):
    ws = Workspace(
        user_id=dev_user.id, name="Orders", prompt="track my orders", status=WorkspaceStatus.READY
    )
    session.add(ws)
    await session.flush()
    assert await runs.workspaces_due_for_sync(session, 10) == []
    session.add(AccessGrant(email=dev_user.email))
    await session.flush()
    assert await runs.workspaces_due_for_sync(session, 10) == [ws.id]


# ------------------------------------------------------------------ /admin/access


async def test_admin_gives_and_takes_back_free_access(client, other_client, admin, no_access):
    assert (await other_client.get("/api/v1/workspaces")).status_code == 402

    r = await client.post(
        "/api/v1/admin/access/grants", json={"email": " Other@Demux.local ", "note": "Beta tester"}
    )
    assert r.status_code == 201, r.text
    g = r.json()
    assert (g["email"], g["note"], g["status"], g["has_account"], g["granted_by"]) == (
        "other@demux.local",
        "Beta tester",
        "active",
        True,
        "dev@demux.local",
    )
    assert (await other_client.get("/api/v1/workspaces")).status_code == 200
    state = (await client.get("/api/v1/admin/access")).json()
    assert [x["email"] for x in state["grants"]] == ["other@demux.local"]
    assert state["stripe_configured"] is False

    r = await client.post(f"/api/v1/admin/access/grants/{g['id']}/revoke")
    assert r.json()["status"] == "revoked"
    assert (await other_client.get("/api/v1/workspaces")).status_code == 402

    # Granting the same email again renews the same grant.
    r = await client.post("/api/v1/admin/access/grants", json={"email": "other@demux.local"})
    assert r.json()["id"] == g["id"] and r.json()["status"] == "active"
    assert (await other_client.get("/api/v1/workspaces")).status_code == 200


async def test_admin_grant_validation(client, admin):
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    r = await client.post(
        "/api/v1/admin/access/grants", json={"email": "a@x.example", "expires_at": past}
    )
    assert r.status_code == 422
    r = await client.post("/api/v1/admin/access/grants", json={"email": "not an email"})
    assert r.status_code == 422
    r = await client.post(f"/api/v1/admin/access/grants/{uuid.uuid4()}/revoke")
    assert r.status_code == 404


async def test_admin_stripe_sync_reconciles(client, session, admin, stripe):
    session.add(
        BillingCustomer(
            stripe_customer_id="cus_gone", email="gone@x.example", subscription_status="active"
        )
    )
    await session.flush()
    stripe.add(customer("cus_1", "payer@x.example"), sub("sub_1", "cus_1", "active"))
    stripe.add(customer("cus_2", "early@x.example"), trialing("sub_2", "cus_2"))
    r = await client.post("/api/v1/admin/access/stripe-sync")
    assert r.json() == {"synced": 2}
    state = (await client.get("/api/v1/admin/access")).json()
    got = {c["email"]: (c["status"], c["active"]) for c in state["customers"]}
    assert got == {
        "payer@x.example": ("active", True),
        "early@x.example": ("trialing", True),
        "gone@x.example": ("deleted", False),
    }


async def test_admin_users_table_shows_access(client, session, admin, other_client, no_access):
    await other_client.get("/api/v1/me")  # creates the second user
    rows = {u["email"]: u["access"] for u in (await client.get("/api/v1/admin/users")).json()}
    assert rows == {"dev@demux.local": "admin", "other@demux.local": "none"}
