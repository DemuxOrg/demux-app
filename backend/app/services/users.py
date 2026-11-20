"""User profile logic: the first and last name shown in the app ("Hello, Maya").

The login columns belong to better-auth, which sets the names at sign-up; edits made on
the profile page come through here. `name` (better-auth's required display name) is kept
as "First Last" so both stay in step.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def rename(session: AsyncSession, user: User, first_name: str, last_name: str) -> User:
    """Set the user's name. Only ever called with the signed-in user."""
    user.first_name = first_name
    user.last_name = last_name
    user.name = f"{first_name} {last_name}".strip()
    await session.flush()
    return user
