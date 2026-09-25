"""Fixtures.

Database-backed tests run inside a transaction that is rolled back afterwards,
so they never leave rows behind and never need a truncate step. Tests that only
exercise a service do not use these fixtures at all -- see test_item_service.py.

If `TEST_DATABASE_URL` is not reachable, the database-backed tests skip with a
message rather than failing, so a fresh clone can run `uv run pytest` before
anything is provisioned. CI always has Postgres, so nothing is skipped there.
"""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from api_base.config import get_settings
from api_base.db import Base, get_session
from api_base.main import create_app

settings = get_settings()


@pytest.fixture(scope="session")
def api_prefix() -> str:
    return settings.api_prefix


@pytest.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    """Session-wide engine with the schema created once and dropped at the end."""
    engine = create_async_engine(settings.test_database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - any driver error means "no database"
        await engine.dispose()
        pytest.skip(
            f"No test database at {settings.test_database_url}: {exc}. "
            "Start one with `docker compose up -d db`."
        )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session bound to an open transaction that is rolled back after the test.

    `join_transaction_mode="create_savepoint"` makes the application's own
    `session.commit()` release a savepoint instead of committing for real, so
    request handlers behave normally and the test still leaves no trace.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        factory = async_sessionmaker(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        async with factory() as session:
            yield session
        await transaction.rollback()


@pytest.fixture
def app(session: AsyncSession) -> AsyncIterator[FastAPI]:
    """The real app, with only the session dependency swapped."""
    application = create_app()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    application.dependency_overrides[get_session] = override_get_session
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
