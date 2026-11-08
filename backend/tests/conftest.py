"""Pytest fixtures shared by all backend tests.

Responsible for:
- Pointing the app at the real Postgres test DB (`demux_test`), not SQLite, because we
  rely on JSONB and enums. Tables are created once per run from the models.
- Isolating each test in a transaction that is rolled back at the end (the app's
  commits only release a SAVEPOINT).
- `client`: an httpx AsyncClient talking to the app in-process, as the dev user.
- `other_client`: same, but authenticated as a different user (for isolation tests).
"""

import os

# Must be set before app modules are imported: tests run with ENV=test on the test DB.
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")
os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+asyncpg://demux:demux@localhost:5432/demux_test"
)
os.environ["ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

from app.api.deps import get_current_user  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(os.environ["TEST_DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    async with engine.connect() as conn:
        outer = await conn.begin()
        async with AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as s:
            yield s
        await outer.rollback()


@pytest.fixture(autouse=True)
def _override_session(session):
    async def _get_session():
        yield session
        await session.commit()

    app.dependency_overrides[get_session] = _get_session
    yield
    app.dependency_overrides.clear()


async def _make_user(session: AsyncSession, email: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email)
        session.add(user)
        await session.flush()
    return user


@pytest_asyncio.fixture
async def client(session) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def other_client(session) -> AsyncIterator[AsyncClient]:
    """A client acting as a second user; shares the same DB transaction as `client`."""
    other = await _make_user(session, "other@demux.local")

    async def _other_user() -> User:
        return other

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Swap the user only for requests made through this client.
        original = c.request

        async def request(*args, **kwargs):
            app.dependency_overrides[get_current_user] = _other_user
            try:
                return await original(*args, **kwargs)
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        c.request = request  # type: ignore[method-assign]
        yield c
