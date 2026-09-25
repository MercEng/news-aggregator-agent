"""Service layer, with a stub repository. No database, no event loop tricks, no
fixtures -- which is the payoff for keeping SQL out of the service.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from api_base.exceptions import ConflictError, NotFoundError, ValidationError
from api_base.item.model import Item
from api_base.item.schema import ItemCreate, ItemUpdate
from api_base.item.service import ItemService


class StubItemRepository:
    """In-memory stand-in for ItemRepository. Duck typed on purpose: the service
    only ever calls these six methods, so nothing else needs to exist."""

    def __init__(self) -> None:
        self.rows: dict[uuid.UUID, Item] = {}

    async def get(self, id: uuid.UUID) -> Item | None:
        return self.rows.get(id)

    async def get_by_name(self, name: str) -> Item | None:
        return next((row for row in self.rows.values() if row.name.lower() == name.lower()), None)

    async def get_many(self, *, limit: int = 50, offset: int = 0, **filters: Any) -> list[Item]:
        matches = [row for row in self.rows.values() if self._matches(row, filters)]
        return matches[offset : offset + limit]

    async def count(self, **filters: Any) -> int:
        return sum(1 for row in self.rows.values() if self._matches(row, filters))

    async def create(self, data: dict[str, Any]) -> Item:
        now = datetime.now(UTC)
        row = Item(id=uuid.uuid4(), created_at=now, updated_at=now, **data)
        self.rows[row.id] = row
        return row

    async def update(self, id: uuid.UUID, data: dict[str, Any]) -> Item | None:
        row = self.rows.get(id)
        if row is None:
            return None
        for field, value in data.items():
            setattr(row, field, value)
        row.updated_at = datetime.now(UTC)
        return row

    async def delete(self, id: uuid.UUID) -> bool:
        return self.rows.pop(id, None) is not None

    @staticmethod
    def _matches(row: Item, filters: dict[str, Any]) -> bool:
        return all(getattr(row, field) == value for field, value in filters.items())


@pytest.fixture
def service() -> ItemService:
    return ItemService(StubItemRepository())


async def test_create_normalises_whitespace_in_the_name(service: ItemService) -> None:
    item = await service.create(ItemCreate(name="  Blue   Widget  "))

    assert item.name == "Blue Widget"


async def test_create_rejects_a_name_that_differs_only_by_case_or_spacing(
    service: ItemService,
) -> None:
    await service.create(ItemCreate(name="Blue Widget"))

    with pytest.raises(ConflictError) as caught:
        await service.create(ItemCreate(name="blue   widget"))

    assert caught.value.details == {"field": "name"}


async def test_create_rejects_a_whitespace_only_name(service: ItemService) -> None:
    with pytest.raises(ValidationError):
        await service.create(ItemCreate(name="   "))


async def test_get_raises_not_found_rather_than_returning_none(service: ItemService) -> None:
    with pytest.raises(NotFoundError):
        await service.get(uuid.uuid4())


async def test_update_leaves_unsent_fields_alone(service: ItemService) -> None:
    created = await service.create(ItemCreate(name="Widget", description="Original"))

    updated = await service.update(created.id, ItemUpdate(is_active=False))

    assert updated.description == "Original"
    assert updated.is_active is False


async def test_update_allows_renaming_an_item_to_its_own_name(service: ItemService) -> None:
    created = await service.create(ItemCreate(name="Widget"))

    updated = await service.update(created.id, ItemUpdate(name="widget"))

    assert updated.name == "widget"


async def test_update_rejects_a_name_owned_by_another_item(service: ItemService) -> None:
    await service.create(ItemCreate(name="Taken"))
    other = await service.create(ItemCreate(name="Free"))

    with pytest.raises(ConflictError):
        await service.update(other.id, ItemUpdate(name="Taken"))


async def test_list_items_reports_the_unpaginated_total(service: ItemService) -> None:
    for index in range(5):
        await service.create(ItemCreate(name=f"Item {index}"))

    page = await service.list_items(limit=2, offset=0)

    assert page.total == 5
    assert len(page.items) == 2


async def test_delete_raises_not_found_for_an_unknown_id(service: ItemService) -> None:
    with pytest.raises(NotFoundError):
        await service.delete(uuid.uuid4())
