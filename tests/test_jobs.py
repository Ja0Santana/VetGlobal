from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_async_session
from app.main import app
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
async def test_complete_job_done_returns_200():
    mock_session = AsyncMock()

    job = Job(document_id=1, status=JobStatus.ENQUEUED)
    job.id = 55
    job.created_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = job
    mock_session.execute.return_value = mock_result

    async def fake_commit():
        pass

    async def fake_refresh(instance):
        pass

    mock_session.commit = fake_commit
    mock_session.refresh = fake_refresh

    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/jobs/55/complete",
            json={
                "status": "DONE",
                "summary": "Patient has a history of intermittent vomiting.",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == 55
    assert data["document_id"] == 1
    assert data["status"] == "DONE"
    assert "completed_at" in data
    assert job.summary == "Patient has a history of intermittent vomiting."
    assert job.error_message is None
    assert job.started_at is not None


@pytest.mark.asyncio
async def test_complete_job_failed_returns_200():
    mock_session = AsyncMock()

    job = Job(document_id=1, status=JobStatus.ENQUEUED)
    job.id = 56
    job.created_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = job
    mock_session.execute.return_value = mock_result

    async def fake_commit():
        pass

    async def fake_refresh(instance):
        pass

    mock_session.commit = fake_commit
    mock_session.refresh = fake_refresh

    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/jobs/56/complete",
            json={
                "status": "FAILED",
                "error": "Could not parse document",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == 56
    assert data["document_id"] == 1
    assert data["status"] == "FAILED"
    assert "completed_at" in data
    assert job.error_message == "Could not parse document"
    assert job.summary is None
    assert job.started_at is not None


@pytest.mark.asyncio
async def test_complete_nonexistent_job_returns_404():
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
            "/internal/jobs/999/complete",
            json={"status": "DONE", "summary": "Sample summary"},
        )

    assert response.status_code == 404
    assert "999" in response.json()["detail"]


@pytest.mark.asyncio
async def test_complete_already_completed_job_returns_409():
    mock_session = AsyncMock()

    job = Job(document_id=1, status=JobStatus.DONE)
    job.id = 55
    job.summary = "Existing summary"
    job.created_at = datetime.now(timezone.utc)
    job.completed_at = datetime.now(timezone.utc)

    mock_none_res = MagicMock()
    mock_none_res.scalar_one_or_none.return_value = None

    mock_job_res = MagicMock()
    mock_job_res.scalar_one_or_none.return_value = job

    mock_session.execute.side_effect = [mock_none_res, mock_job_res]

    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/jobs/55/complete",
            json={"status": "DONE", "summary": "Another summary"},
        )

    assert response.status_code == 409
    assert "already completed" in response.json()["detail"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"status": "DONE"},
        {"status": "DONE", "summary": ""},
        {"status": "DONE", "summary": "   "},
        {"status": "FAILED"},
        {"status": "FAILED", "error": ""},
        {"status": "FAILED", "error": "   "},
        {"status": "ENQUEUED", "summary": "Invalid"},
    ],
)
async def test_complete_job_invalid_payload_returns_422(invalid_payload):
    mock_session = AsyncMock()
    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/internal/jobs/55/complete",
            json=invalid_payload,
        )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_id", [0, -1, -50])
async def test_complete_job_invalid_id_returns_422(invalid_id):
    mock_session = AsyncMock()
    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/internal/jobs/{invalid_id}/complete",
            json={"status": "DONE", "summary": "Valid summary"},
        )

    assert response.status_code == 422
