"""Wiring for this feature -- no logic.

Keeping it in the feature means the router depends on `ItemServiceDep` and a
test can swap any single link in the chain (session, repository, or service)
with one `app.dependency_overrides` entry.
"""

from typing import Annotated

from fastapi import Depends

from api_base.dependencies import SessionDep
from api_base.item.repository import ItemRepository
from api_base.item.service import ItemService


def get_item_repository(session: SessionDep) -> ItemRepository:
    return ItemRepository(session)


ItemRepositoryDep = Annotated[ItemRepository, Depends(get_item_repository)]


def get_item_service(repository: ItemRepositoryDep) -> ItemService:
    return ItemService(repository)


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]
