"""Read-only Stripe REST client and webhook signature verification.

Demux bills through the landing page (www.usedemux.com), which owns checkout. This API
only *reads* Stripe to decide who may use the app: customers (email, the trial dates the
landing page puts in their metadata) and their subscriptions. It never creates, changes
or charges anything, so a restricted key (Customers: read, Subscriptions: read) is enough.

Plain httpx instead of the SDK: four GET calls and one HMAC check. The API version is
pinned to the landing page's, so both read the same object shapes.
"""

import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

API_BASE = "https://api.stripe.com/v1"
API_VERSION = "2026-07-29.dahlia"  # same as the landing page's Stripe clients
SIGNATURE_TOLERANCE_S = 300  # Stripe's default: reject events signed more than 5 min ago


class StripeError(Exception):
    """Stripe could not be reached or refused the call (never includes the key)."""


class SignatureError(Exception):
    """A webhook request that Stripe did not sign with our endpoint's secret."""


def verify_webhook(
    payload: bytes,
    header: str | None,
    secret: str,
    *,
    now: float | None = None,
    tolerance_s: int = SIGNATURE_TOLERANCE_S,
) -> dict[str, Any]:
    """Check the `Stripe-Signature` header and return the parsed event.

    The header is `t=<unix>,v1=<hex>[,v1=<hex>…]`; each v1 is HMAC-SHA256 of
    `"<t>.<raw body>"` with the endpoint's signing secret. Several v1 values appear while
    a secret is being rolled.
    """
    if not header or not secret:
        raise SignatureError("missing signature")
    timestamp: int | None = None
    signatures: list[str] = []
    for part in header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError as e:
                raise SignatureError("bad timestamp") from e
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or not signatures:
        raise SignatureError("malformed signature header")
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in signatures):
        raise SignatureError("signature mismatch")
    if abs((now if now is not None else time.time()) - timestamp) > tolerance_s:
        raise SignatureError("signature too old")
    try:
        event = json.loads(payload)
    except ValueError as e:
        raise SignatureError("body is not JSON") from e
    if not isinstance(event, dict):
        raise SignatureError("body is not an event")
    return event


class StripeClient:
    """The calls the access rule needs. Use as `async with StripeClient(key) as stripe:`."""

    def __init__(self, api_key: str, *, transport: httpx.AsyncBaseTransport | None = None):
        self._http = httpx.AsyncClient(
            base_url=API_BASE,
            auth=(api_key, ""),
            headers={"Stripe-Version": API_VERSION},
            timeout=20,
            transport=transport,
        )

    async def __aenter__(self) -> "StripeClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._http.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        try:
            r = await self._http.get(path, params=params)
        except httpx.HTTPError as e:
            raise StripeError(f"Stripe unreachable ({type(e).__name__})") from e
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            try:
                err = r.json().get("error") or {}
            except ValueError:
                err = {}
            code = err.get("code") or err.get("type") or "error"
            raise StripeError(f"Stripe returned {r.status_code} ({code})")
        return r.json()

    async def _list(self, path: str, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        params = {**params, "limit": 100}
        while True:
            page = await self._get(path, params)
            if not page:
                return
            items = page.get("data") or []
            for item in items:
                yield item
            if not page.get("has_more") or not items:
                return
            params["starting_after"] = items[-1]["id"]

    async def customer(self, customer_id: str) -> dict[str, Any] | None:
        """The customer, `{"id", "deleted": True}` once deleted, or None if unknown."""
        return await self._get(f"/customers/{customer_id}")

    async def customers(self, email: str | None = None) -> AsyncIterator[dict[str, Any]]:
        """Every live customer (deleted ones are not listed), or those with this email."""
        async for c in self._list("/customers", {"email": email} if email else {}):
            yield c

    async def subscriptions(self, customer_id: str | None = None) -> list[dict[str, Any]]:
        """Subscriptions in every status (canceled too), of one customer or of all."""
        params: dict[str, Any] = {"status": "all"}
        if customer_id:
            params["customer"] = customer_id
        return [s async for s in self._list("/subscriptions", params)]
