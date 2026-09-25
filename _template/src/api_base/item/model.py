"""Layer: model. The table, and nothing else. Never leaves this package."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from api_base.db import TimestampedBase


class Item(TimestampedBase):
    __tablename__ = "items"

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
