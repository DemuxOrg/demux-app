"""Shared FastAPI dependencies.

`get_current_user` resolves the better-auth session cookie (set by the Next.js login
pages) to a verified user. With `ENV=test` and no cookie, it falls back to a fixed dev
user (`dev@demux.local`, with a connected Gmail) so the test suite can call the API
without signing in. That stub exists only in tests.

`get_admin_user` guards every `/admin` route: no session is 401 like everywhere else;
a signed-in non-admin gets the same 404 as an unknown URL, so the routes stay invisible.
Each admin request is written to `admin_audit`.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from app.auth.crypto import encrypt
from app.auth.session import session_token_from_cookies, user_for_session_token
from app.core.config import Env, settings
from app.core.errors import UnauthorizedError
from app.db.session import get_session
from app.models.user import User
from app.services import admin_audit

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


def is_admin(user: User) -> bool:
    return user.is_admin or user.email.lower() in settings.admin_emails


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
