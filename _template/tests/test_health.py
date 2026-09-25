import pytest
from httpx import AsyncClient


async def test_liveness_does_not_need_the_database(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_readiness_reports_the_database(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_readiness_is_503_when_the_database_is_unreachable(
    client: AsyncClient, api_prefix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unreachable(_session: object) -> bool:
        return False

    monkeypatch.setattr("api_base.routers.health.ping", unreachable)

    response = await client.get(f"{api_prefix}/health/ready")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


async def test_unknown_route_uses_the_shared_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
