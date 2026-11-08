"""Async database engine and session dependency.

Responsible for creating the single async SQLAlchemy engine (asyncpg) and providing
`get_session`, the FastAPI dependency that hands each request one session. The
session commits when the request succeeds and rolls back if it raises, so services
only need to `flush()`.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
