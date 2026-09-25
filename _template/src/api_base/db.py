"""Database plumbing shared by every feature: the declarative base, the engine,
and the request-scoped session.

The transaction boundary lives here: one request is one transaction.
Repositories flush so they can read back generated values, but only
`get_session` commits.
"""

import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, Uuid, func, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from api_base.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


# --- declarative base ---------------------------------------------------

# Deterministic constraint names mean the schema this metadata describes matches
# what the migrations repository creates, and stay stable across changes.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampedBase(Base):
    """Abstract parent for real tables: a UUID primary key and audit timestamps."""

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# --- engine and session -------------------------------------------------

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

session_factory = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a session, committing on success and rolling back on any exception."""
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def ping(session: AsyncSession) -> bool:
    """True if the database answers. Used by the readiness probe.

    Catches bare `Exception` deliberately. A refused TCP connection surfaces as
    an `OSError` from asyncpg, not a `SQLAlchemyError` -- SQLAlchemy only wraps
    errors the driver raises as DBAPI errors. For a readiness check, anything
    that stops us reaching the database means "not ready".
    """
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.warning("readiness probe: database unreachable", exc_info=True)
        return False
    return True


async def dispose_engine() -> None:
    """Close pooled connections. Called from the app lifespan on shutdown."""
    await engine.dispose()
