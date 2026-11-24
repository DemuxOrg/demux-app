"""Audit trail for /admin: who looked at what, and when (one row per admin request)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminAudit
from app.models.user import User


async def record(
    session: AsyncSession, admin: User, *, method: str, action: str, target: dict[str, Any]
) -> None:
    session.add(
        AdminAudit(
            admin_user_id=admin.id,
            admin_email=admin.email,
            method=method,
            action=action,
            target={k: str(v) for k, v in target.items()},
        )
    )
    await session.flush()
