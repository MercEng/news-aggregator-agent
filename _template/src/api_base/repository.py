"""Generic CRUD repository, shared by every feature.

Each feature subclasses this in its own `repository.py` and adds only the
queries the base class does not cover.

Repositories `flush()` rather than `commit()`. Flushing sends the SQL so
generated columns can be read back, but leaves the transaction open -- the
request-scoped `get_session` dependency in `db.py` decides commit vs rollback.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_base.db import TimestampedBase


class BaseRepository[ModelT: TimestampedBase]:
    """CRUD over one mapped class. Subclasses get typed returns for free."""

    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def get_many(
        self, *, limit: int = 50, offset: int = 0, **filters: Any
    ) -> Sequence[ModelT]:
        """Newest first, with `id` as a tiebreak so paging is stable."""
        stmt = (
            select(self.model)
            .where(*self._conditions(filters))
            .order_by(self.model.created_at.desc(), self.model.id)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.scalars(stmt)
        return result.all()

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model).where(*self._conditions(filters))
        return await self.session.scalar(stmt) or 0

    async def create(self, data: dict[str, Any]) -> ModelT:
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: uuid.UUID, data: dict[str, Any]) -> ModelT | None:
        instance = await self.get(id)
        if instance is None:
            return None
        for field, value in data.items():
            setattr(instance, field, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: uuid.UUID) -> bool:
        instance = await self.get(id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True

    def _conditions(self, filters: dict[str, Any]) -> list[ColumnElement[bool]]:
        """Turn `field=value` kwargs into equality clauses, rejecting typos loudly."""
        conditions: list[ColumnElement[bool]] = []
        for field, value in filters.items():
            if field not in self.model.__mapper__.columns:
                raise ValueError(f"{self.model.__name__} has no column named {field!r}")
            conditions.append(getattr(self.model, field) == value)
        return conditions
