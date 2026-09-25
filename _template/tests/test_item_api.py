"""Router layer, exercised over HTTP against a real database."""

import uuid

from httpx import AsyncClient


async def create_item(client: AsyncClient, api_prefix: str, **overrides: object) -> dict:
    payload = {"name": "Blue Widget", "description": "A widget."} | overrides
    response = await client.post(f"{api_prefix}/items", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


async def test_create_returns_201_and_the_created_item(
    client: AsyncClient, api_prefix: str
) -> None:
    body = await create_item(client, api_prefix)

    assert body["name"] == "Blue Widget"
    assert body["is_active"] is True
    assert uuid.UUID(body["id"])
    assert body["created_at"] and body["updated_at"]


async def test_create_rejects_a_duplicate_name_with_409(
    client: AsyncClient, api_prefix: str
) -> None:
    await create_item(client, api_prefix, name="Gadget")

    response = await client.post(f"{api_prefix}/items", json={"name": "  gadget  "})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_get_returns_the_item(client: AsyncClient, api_prefix: str) -> None:
    created = await create_item(client, api_prefix)

    response = await client.get(f"{api_prefix}/items/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_returns_404_in_the_shared_envelope(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/items/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_list_paginates(client: AsyncClient, api_prefix: str) -> None:
    for index in range(5):
        await create_item(client, api_prefix, name=f"Item {index}")

    response = await client.get(f"{api_prefix}/items", params={"limit": 2, "offset": 1})

    body = response.json()
    assert response.status_code == 200
    assert body["total"] == 5
    assert body["limit"] == 2
    assert body["offset"] == 1
    assert len(body["items"]) == 2


async def test_list_filters_on_is_active(client: AsyncClient, api_prefix: str) -> None:
    await create_item(client, api_prefix, name="Live one")
    await create_item(client, api_prefix, name="Dead one", is_active=False)

    response = await client.get(f"{api_prefix}/items", params={"is_active": False})

    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Dead one"


async def test_patch_updates_only_the_fields_sent(client: AsyncClient, api_prefix: str) -> None:
    created = await create_item(client, api_prefix)

    response = await client.patch(f"{api_prefix}/items/{created['id']}", json={"is_active": False})

    body = response.json()
    assert response.status_code == 200
    assert body["is_active"] is False
    assert body["description"] == "A widget."


async def test_patch_to_a_taken_name_is_a_409(client: AsyncClient, api_prefix: str) -> None:
    await create_item(client, api_prefix, name="Taken")
    other = await create_item(client, api_prefix, name="Free")

    response = await client.patch(f"{api_prefix}/items/{other['id']}", json={"name": "Taken"})

    assert response.status_code == 409


async def test_delete_returns_204_then_404(client: AsyncClient, api_prefix: str) -> None:
    created = await create_item(client, api_prefix)

    deleted = await client.delete(f"{api_prefix}/items/{created['id']}")
    assert deleted.status_code == 204

    assert (await client.get(f"{api_prefix}/items/{created['id']}")).status_code == 404


async def test_invalid_body_uses_the_shared_error_envelope(
    client: AsyncClient, api_prefix: str
) -> None:
    response = await client.post(f"{api_prefix}/items", json={"name": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
