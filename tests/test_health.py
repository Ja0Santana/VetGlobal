import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.core.database import get_async_session


@pytest.mark.asyncio
async def test_health_check_healthy_with_mocked_session():
    mock_session = AsyncMock()
    mock_session.execute.return_value = None

    async def override_get_async_session():
        yield mock_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_health_check_database_failure():
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("Connection refused")

    async def override_get_async_session():
        yield mock_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/health")

    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "Database connectivity failed" in response.json()["detail"]
