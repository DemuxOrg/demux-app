"""Shared FastAPI dependencies.

`get_current_user` resolves the better-auth session cookie (set by the Next.js login
pages) to a verified user. With `ENV=test` and no cookie, it falls back to a fixed dev
user (`dev@demux.local`, with a connected Gmail) so the test suite can call the API
without signing in. That stub exists only in tests.

`get_entitled_user` guards the app itself (workspaces): a signed-in user without a
subscription, trial or free access gets 402 `subscription_required` (see
app/services/access.py). `/me` stays open so the frontend can show why.

`get_admin_user` guards every `/admin` route: no session is 401 like everywhere else;
a signed-in non-admin gets the same 404 as an unknown URL, so the routes stay invisible.
Each admin request is written to `admin_audit`.

`get_stripe` is the read-only Stripe client, or None when STRIPE_SECRET_KEY is unset.
"""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from app.auth.crypto import encrypt
from app.auth.session import session_token_from_cookies, user_for_session_token
from app.billing.stripe_api import StripeClient
from app.core.config import Env, settings
from app.core.errors import PaymentRequiredError, UnauthorizedError
from app.db.session import get_session
from app.models.user import User
from app.services import access, admin_audit

DEV_USER_EMAIL = "dev@demux.local"

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(request: Request, session: SessionDep) -> User:
    token = session_token_from_cookies(request.cookies)
    if token:
        user = await user_for_session_token(session, token)
        if user is not None:
            return user
        raise UnauthorizedError("Session expired. Sign in again.")
    if settings.ENV == Env.TEST:
        user = await session.scalar(select(User).where(User.email == DEV_USER_EMAIL))
        if user is None:
            user = User(
                email=DEV_USER_EMAIL,
                email_verified=True,
                gmail_email=DEV_USER_EMAIL,
                refresh_token_enc=encrypt("test-refresh-token"),
            )
            session.add(user)
            await session.flush()
        return user
    raise UnauthorizedError("Sign in required.")


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_entitled_user(user: CurrentUser, session: SessionDep) -> User:
    if not (await access.for_user(session, user)).allowed:
        raise PaymentRequiredError(
            "Your Demux access has ended. Subscribe to keep using your workspaces."
        )
    return user


EntitledUser = Annotated[User, Depends(get_entitled_user)]


def is_admin(user: User) -> bool:
    return user.is_admin or access.is_admin_email(user.email)


async def get_admin_user(request: Request, user: CurrentUser, session: SessionDep) -> User:
    if not is_admin(user):
        raise HTTPException(status_code=404, detail="Not Found")
    route = request.scope.get("route")
    await admin_audit.record(
        session,
        user,
        method=request.method,
        action=getattr(route, "path", request.url.path),
        target={**request.path_params, **request.query_params},
    )
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]


async def get_stripe() -> AsyncIterator[StripeClient | None]:
    if not settings.STRIPE_SECRET_KEY:
        yield None
        return
    async with StripeClient(settings.STRIPE_SECRET_KEY) as client:
        yield client


StripeDep = Annotated[StripeClient | None, Depends(get_stripe)]
