"""Layer: schema. The public contract -- what a client may send and may see.

Distinct from `model.py` on purpose: `ItemCreate` has no `id`, `ItemPage` has no
table behind it, and a column you add to the table is not automatically exposed.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool = True


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    """Every field optional: this is a PATCH body."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ItemPage(BaseModel):
    """One page of results plus the totals a client needs to paginate."""

    items: list[ItemRead]
    total: int
    limit: int
    offset: int
