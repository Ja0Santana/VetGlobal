import io
import os
import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.main import app
from app.core.database import get_async_session
from app.models.pet import Pet
from app.models.document import Document
from app.models.job import Job
from app.models.job_status import JobStatus


def _override_session(mock_session):
    async def _override():
        yield mock_session
    app.dependency_overrides[get_async_session] = _override


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_document_returns_202():
    mock_session = AsyncMock()

    pet = Pet(name="Hank", owner_name="John")
    pet.id = 1
    pet.created_at = datetime.now(timezone.utc)

    mock_result_pet = MagicMock()
    mock_result_pet.scalar_one_or_none.return_value = pet

    mock_result_dup = MagicMock()
    mock_result_dup.scalar_one_or_none.return_value = None

    mock_session.execute.side_effect = [mock_result_pet, mock_result_dup]

    document_id_counter = 10
    job_id_counter = 55

    async def fake_flush():
        pass

    async def fake_commit():
        pass

    async def fake_refresh(instance):
        if isinstance(instance, Document):
            instance.id = document_id_counter
            instance.created_at = datetime.now(timezone.utc)
        elif isinstance(instance, Job):
            instance.id = job_id_counter
            instance.status = JobStatus.ENQUEUED
            instance.created_at = datetime.now(timezone.utc)

    mock_session.flush = fake_flush
    mock_session.commit = fake_commit
    mock_session.refresh = fake_refresh
    mock_session.add = MagicMock()

    _override_session(mock_session)

    file_content = b"Patient Hank has a history of intermittent vomiting."

    with patch("app.services.document_service.aiofiles") as mock_aiofiles:
        mock_file_ctx = AsyncMock()
        mock_file_ctx.write = AsyncMock()
        mock_aiofiles.open.return_value.__aenter__ = AsyncMock(
            return_value=mock_file_ctx
        )
        mock_aiofiles.open.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("os.makedirs"), patch("os.replace"), patch("os.path.exists", return_value=False):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/pets/1/documents",
                    files={"file": ("prontuario.txt", io.BytesIO(file_content), "text/plain")},
                )

    assert response.status_code == 202
    data = response.json()
    assert data["document_id"] == 10
    assert data["job_id"] == 55
    assert data["status"] == "ENQUEUED"


@pytest.mark.asyncio
async def test_upload_invalid_extension_returns_400():
    mock_session = AsyncMock()
    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/pets/1/documents",
            files={"file": ("image.jpg", io.BytesIO(b"fake"), "image/jpeg")},
        )

    assert response.status_code == 400
    assert "unsupported extension" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_for_nonexistent_pet_returns_404():
    mock_session = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/pets/999/documents",
            files={"file": ("doc.txt", io.BytesIO(b"content"), "text/plain")},
        )

    assert response.status_code == 404
    assert "999" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_duplicate_returns_409():
    mock_session = AsyncMock()

    pet = Pet(name="Hank", owner_name="John")
    pet.id = 1
    pet.created_at = datetime.now(timezone.utc)

    existing_doc = Document(
        pet_id=1,
        filename="doc.txt",
        file_path="/fake/path",
        file_hash="abc123",
    )
    existing_doc.id = 5

    mock_result_pet = MagicMock()
    mock_result_pet.scalar_one_or_none.return_value = pet

    mock_result_dup = MagicMock()
    mock_result_dup.scalar_one_or_none.return_value = existing_doc

    mock_session.execute.side_effect = [mock_result_pet, mock_result_dup]

    _override_session(mock_session)

    file_content = b"Some document content"

    with patch("app.services.document_service.aiofiles") as mock_aiofiles:
        mock_file_ctx = AsyncMock()
        mock_file_ctx.write = AsyncMock()
        mock_aiofiles.open.return_value.__aenter__ = AsyncMock(
            return_value=mock_file_ctx
        )
        mock_aiofiles.open.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("os.makedirs"), patch("os.replace"), patch("os.path.exists", return_value=True), patch("os.remove"):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/pets/1/documents",
                    files={"file": ("doc.txt", io.BytesIO(file_content), "text/plain")},
                )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
