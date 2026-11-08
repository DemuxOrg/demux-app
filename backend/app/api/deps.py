"""Shared FastAPI dependencies.

Responsible for `get_current_user`, the single place that decides who is calling.
PHASE 0 STUB: in `ENV=dev|test` it returns (creating if missing) a fixed dev user
`dev@demux.local`; in `ENV=prod` it raises 401 so the stub can never silently ship.
Phase 1 replaces this one function with real Google OAuth session auth.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Env, settings
from app.core.errors import UnauthorizedError
from app.db.session import get_session
from app.models.user import User

DEV_USER_EMAIL = "dev@demux.local"

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(session: SessionDep) -> User:
    if settings.ENV == Env.PROD:
        raise UnauthorizedError("Authentication required.")
    user = await session.scalar(select(User).where(User.email == DEV_USER_EMAIL))
    if user is None:
        user = User(email=DEV_USER_EMAIL)
        session.add(user)
        await session.flush()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
