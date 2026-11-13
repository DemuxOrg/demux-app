"""Shared FastAPI dependencies.

`get_current_user` reads the signed session cookie set by the Google OAuth callback.
With `ENV=test` and no cookie, it falls back to a fixed dev user (`dev@demux.local`) so
the test suite can call the API without signing in. That stub exists only in tests.
"""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session import SESSION_COOKIE, read_session_token
from app.core.config import Env, settings
from app.core.errors import UnauthorizedError
from app.db.session import get_session
from app.models.user import User

DEV_USER_EMAIL = "dev@demux.local"

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        user_id = read_session_token(token)
        user = await session.get(User, user_id) if user_id else None
        if user is not None:
            return user
        raise UnauthorizedError("Session expired. Sign in again.")
    if settings.ENV == Env.TEST:
        user = await session.scalar(select(User).where(User.email == DEV_USER_EMAIL))
        if user is None:
            user = User(email=DEV_USER_EMAIL)
            session.add(user)
            await session.flush()
        return user
    raise UnauthorizedError("Sign in required.")


CurrentUser = Annotated[User, Depends(get_current_user)]
