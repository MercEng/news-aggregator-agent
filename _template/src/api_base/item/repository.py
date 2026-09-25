"""Layer: repository. All SQL for items. Returns models or `None`, never raises HTTP.

This file is short on purpose: `BaseRepository` does CRUD, and a subclass exists
only to hold the queries that are specific to one entity.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_base.item.model import Item
from api_base.repository import BaseRepository


class ItemRepository(BaseRepository[Item]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Item, session)

    async def get_by_name(self, name: str) -> Item | None:
        """Case-insensitive lookup, used by the service to enforce unique names."""
        stmt = select(Item).where(func.lower(Item.name) == name.lower())
        return await self.session.scalar(stmt)
