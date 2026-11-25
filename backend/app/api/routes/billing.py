"""Server-to-server endpoints that keep access in step with Stripe. Not in the OpenAPI
schema: browsers never call them.

- `POST /billing/stripe/webhook`: Stripe calls it when a customer, subscription or
  checkout changes. Verified with STRIPE_WEBHOOK_SECRET (this endpoint's own secret in the
  Stripe dashboard, not the landing page's), then the customer is re-read from Stripe.
- `POST /internal/signup-check`: the frontend server asks it before better-auth creates
  an account (frontend/src/lib/auth.ts). Authorized by `Authorization: Bearer
  <INTERNAL_API_SECRET>`.
"""

import hmac
import logging

from fastapi import APIRouter, Request

from app.api.deps import SessionDep, StripeDep
from app.billing.stripe_api import SignatureError, StripeError, verify_webhook
from app.core.config import settings
from app.core.errors import AppError, UnauthorizedError
from app.schemas.billing import SignupCheck, SignupVerdict
from app.services import access, billing

logger = logging.getLogger(__name__)

router = APIRouter(include_in_schema=False)


class NotConfiguredError(AppError):
    status_code = 503
    code = "not_configured"


class BadSignatureError(AppError):
    status_code = 400
    code = "bad_signature"


class StripeUnavailableError(AppError):
    status_code = 502
    code = "stripe_unavailable"


@router.post("/billing/stripe/webhook")
async def stripe_webhook(request: Request, session: SessionDep, stripe: StripeDep) -> dict:
    if not settings.STRIPE_WEBHOOK_SECRET or stripe is None:
        raise NotConfiguredError("Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET.")
    try:
        # The raw bytes: the signature covers the exact body Stripe sent.
        event = verify_webhook(
            await request.body(),
            request.headers.get("stripe-signature"),
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except SignatureError as e:
        logger.warning("stripe webhook rejected: %s", e)
        raise BadSignatureError("Invalid Stripe signature.") from e
    try:
        await billing.handle_event(session, stripe, event)
    except StripeError as e:
        # Not acknowledged: Stripe retries the event later.
        logger.warning("stripe webhook %s failed: %s", event.get("id"), e)
        raise StripeUnavailableError("Could not read the customer from Stripe.") from e
    return {"received": True}


def _authorized(request: Request) -> bool:
    expected = f"Bearer {settings.INTERNAL_API_SECRET}"
    given = request.headers.get("authorization", "")
    return hmac.compare_digest(given.encode(), expected.encode())


@router.post("/internal/signup-check", response_model=SignupVerdict)
async def signup_check(
    body: SignupCheck, request: Request, session: SessionDep, stripe: StripeDep
) -> SignupVerdict:
    if not settings.INTERNAL_API_SECRET:
        raise NotConfiguredError("Set INTERNAL_API_SECRET on the API and the frontend.")
    if not _authorized(request):
        raise UnauthorizedError("Bad internal credentials.")
    try:
        verdict = await access.signup_check(session, body.email, stripe)
    except StripeError as e:
        # Fail closed: no account without a confirmed subscription.
        logger.warning("signup check could not reach Stripe: %s", e)
        verdict = await access.for_email(session, body.email)
    logger.info("signup check: %s", verdict.status.value)
    return SignupVerdict(allowed=verdict.allowed)
