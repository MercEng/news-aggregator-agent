"""Layer: service. All business rules for items. No SQL, no `HTTPException`.

Note what is here that a plain CRUD passthrough would not have: name
normalisation and the unique-name rule, enforced on both create and rename.
That rule cannot live in the router (it needs a lookup) and should not live in
the repository (it is a policy, not a query), which is the whole argument for
this layer existing.
"""

import uuid

from api_base.exceptions import ConflictError, NotFoundError, ValidationError
from api_base.item.repository import ItemRepository
from api_base.item.schema import ItemCreate, ItemPage, ItemRead, ItemUpdate


class ItemService:
    def __init__(self, repository: ItemRepository) -> None:
        self.repository = repository

    async def get(self, item_id: uuid.UUID) -> ItemRead:
        item = await self.repository.get(item_id)
        if item is None:
            raise NotFoundError(f"No item with id {item_id}.")
        return ItemRead.model_validate(item)

    async def list_items(
        self, *, limit: int = 50, offset: int = 0, is_active: bool | None = None
    ) -> ItemPage:
        filters = {} if is_active is None else {"is_active": is_active}
        items = await self.repository.get_many(limit=limit, offset=offset, **filters)
        total = await self.repository.count(**filters)
        return ItemPage(
            items=[ItemRead.model_validate(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def create(self, payload: ItemCreate) -> ItemRead:
        name = self._normalise_name(payload.name)
        if await self.repository.get_by_name(name) is not None:
            raise ConflictError(
                f"An item named {name!r} already exists.", details={"field": "name"}
            )
        item = await self.repository.create(
            {
                "name": name,
                "description": payload.description,
                "is_active": payload.is_active,
            }
        )
        return ItemRead.model_validate(item)

    async def update(self, item_id: uuid.UUID, payload: ItemUpdate) -> ItemRead:
        item = await self.repository.get(item_id)
        if item is None:
            raise NotFoundError(f"No item with id {item_id}.")

        # exclude_unset so PATCH means "change what was sent", not "null the rest".
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return ItemRead.model_validate(item)

        if "name" in data:
            name = self._normalise_name(data["name"])
            clash = await self.repository.get_by_name(name)
            if clash is not None and clash.id != item_id:
                raise ConflictError(
                    f"An item named {name!r} already exists.", details={"field": "name"}
                )
            data["name"] = name

        updated = await self.repository.update(item_id, data)
        if updated is None:
            raise NotFoundError(f"No item with id {item_id}.")
        return ItemRead.model_validate(updated)

    async def delete(self, item_id: uuid.UUID) -> None:
        if not await self.repository.delete(item_id):
            raise NotFoundError(f"No item with id {item_id}.")

    @staticmethod
    def _normalise_name(name: str) -> str:
        """Collapse whitespace so " Blue  Widget " and "Blue Widget" collide."""
        cleaned = " ".join(name.split())
        if not cleaned:
            raise ValidationError("Item name cannot be blank.", details={"field": "name"})
        return cleaned
