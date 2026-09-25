"""Layer: router. Schema binding, status codes, and one service call each.

There is no `try`/`except` anywhere below. `NotFoundError` and `ConflictError`
become 404 and 409 via the handlers registered in `exceptions.py`.
"""

import uuid

from fastapi import APIRouter, Query, Response, status

from api_base.item.dependencies import ItemServiceDep
from api_base.item.schema import ItemCreate, ItemPage, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
)
async def create_item(payload: ItemCreate, service: ItemServiceDep) -> ItemRead:
    return await service.create(payload)


@router.get("", response_model=ItemPage, summary="List items")
async def list_items(
    service: ItemServiceDep,
    limit: int = Query(50, ge=1, le=200, description="Page size."),
    offset: int = Query(0, ge=0, description="Rows to skip."),
    is_active: bool | None = Query(None, description="Filter by active flag."),
) -> ItemPage:
    return await service.list_items(limit=limit, offset=offset, is_active=is_active)


@router.get("/{item_id}", response_model=ItemRead, summary="Get an item")
async def get_item(item_id: uuid.UUID, service: ItemServiceDep) -> ItemRead:
    return await service.get(item_id)


@router.patch("/{item_id}", response_model=ItemRead, summary="Update an item")
async def update_item(item_id: uuid.UUID, payload: ItemUpdate, service: ItemServiceDep) -> ItemRead:
    return await service.update(item_id, payload)


# 204 has no body by definition, so this is the one endpoint without a
# response_model -- FastAPI errors if you declare one alongside a 204.
@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete an item",
)
async def delete_item(item_id: uuid.UUID, service: ItemServiceDep) -> Response:
    await service.delete(item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
