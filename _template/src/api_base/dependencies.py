"""Shared dependencies. Feature-specific wiring lives in `<feature>/dependencies.py`."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api_base.db import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
