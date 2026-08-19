import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.main import app
from app.core.database import get_async_session
from app.models.pet import Pet


def _create_mock_session():
    return AsyncMock()


def _override_session(mock_session):
    async def _override():
        yield mock_session
    app.dependency_overrides[get_async_session] = _override


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_pet_returns_201():
    mock_session = _create_mock_session()

    created_pet = Pet(name="Hank", owner_name="John Bergeson")
    created_pet.id = 1
    created_pet.created_at = datetime.now(timezone.utc)

    async def fake_commit():
        pass

    async def fake_refresh(instance):
        instance.id = created_pet.id
        instance.created_at = created_pet.created_at

    mock_session.commit = fake_commit
    mock_session.refresh = fake_refresh
    mock_session.add = MagicMock()

    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/pets",
            json={"name": "Hank", "owner_name": "John Bergeson"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Hank"
    assert data["owner_name"] == "John Bergeson"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_pet_returns_200():
    mock_session = _create_mock_session()

    pet = Pet(name="Hank", owner_name="John Bergeson")
    pet.id = 1
    pet.created_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = pet
    mock_session.execute.return_value = mock_result

    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/pets/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Hank"


@pytest.mark.asyncio
async def test_get_pet_returns_404_when_not_found():
    mock_session = _create_mock_session()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/pets/999")

    assert response.status_code == 404
    assert "999" in response.json()["detail"]
