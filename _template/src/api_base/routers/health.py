"""Liveness and readiness probes.

These are the one place a router touches infrastructure directly: there is no
domain below them to delegate to. The SQL itself still lives in `db.py`.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api_base.config import get_settings
from api_base.db import ping
from api_base.dependencies import SessionDep

router = APIRouter(prefix="/health", tags=["health"])


class Liveness(BaseModel):
    status: str
    app: str
    environment: str


class Readiness(BaseModel):
    status: str
    database: str


@router.get("/live", response_model=Liveness, summary="Liveness probe")
async def live() -> Liveness:
    """Cheap: proves the process is up and serving. Never touches the database."""
    settings = get_settings()
    return Liveness(status="ok", app=settings.app_name, environment=settings.environment)


@router.get(
    "/ready",
    response_model=Readiness,
    summary="Readiness probe",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Database unreachable"}},
)
async def ready(session: SessionDep) -> Readiness:
    """Proves the app can reach its dependencies. Use this to gate traffic."""
    if not await ping(session):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not reachable.",
        )
    return Readiness(status="ok", database="ok")
