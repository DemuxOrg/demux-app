"""Shared FastAPI dependencies.

`get_current_user` resolves the better-auth session cookie (set by the Next.js login
pages) to a verified user. With `ENV=test` and no cookie, it falls back to a fixed dev
user (`dev@demux.local`, with a connected Gmail) so the test suite can call the API
without signing in. That stub exists only in tests.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.crypto import encrypt
from app.auth.session import session_token_from_cookies, user_for_session_token
from app.core.config import Env, settings
from app.core.errors import UnauthorizedError
from app.db.session import get_session
from app.models.user import User

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
