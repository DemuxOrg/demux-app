"""Mail volume per user (admin usage stats), counted from Gmail message ids only.

The worker calls `missing_days` then `save_count` about once an hour. Each user gets one
row per finished UTC day (`date`), covering the last `BACKFILL_DAYS` days, so a newly
connected user has a 7-day average at once and a worker outage leaves no hole.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.usage import MailboxDailyStat
from app.models.user import User

BACKFILL_DAYS = 7


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def missing_days(
    session: AsyncSession, today: date | None = None
) -> list[tuple[uuid.UUID, list[date]]]:
    """(user, days to count) for every user whose Gmail can be read."""
    today = today or datetime.now(UTC).date()
    days = [today - timedelta(days=i) for i in range(1, BACKFILL_DAYS + 1)]
    users = list(
        await session.scalars(
            select(User.id).where(
                User.needs_reconnect.is_(False),
                true() if settings.uses_fake_mailbox else User.refresh_token_enc.is_not(None),
            )
        )
    )
    if not users:
        return []
    have: dict[uuid.UUID, set[date]] = {}
    for user_id, day in await session.execute(
        select(MailboxDailyStat.user_id, MailboxDailyStat.date).where(
            MailboxDailyStat.user_id.in_(users), MailboxDailyStat.date >= days[-1]
        )
    ):
        have.setdefault(user_id, set()).add(day)
    out = []
    for user_id in users:
        todo = [d for d in days if d not in have.get(user_id, set())]
        if todo:
            out.append((user_id, todo))
    return out


async def save_count(session: AsyncSession, user_id: uuid.UUID, day: date, count: int) -> None:
    stmt = insert(MailboxDailyStat).values(user_id=user_id, date=day, messages_received=count)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "date"], set_={"messages_received": count}
        )
    )
