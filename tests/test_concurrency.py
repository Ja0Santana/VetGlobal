import asyncio
import io
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_async_session
from app.core.storage import InMemoryStorageProvider, get_storage_provider
from app.main import app
from app.models.document import Document
from app.models.job import Job
from app.models.job_status import JobStatus
from app.models.pet import Pet
from app.services.document_service import DocumentService


def _override_session(mock_session):
    if not hasattr(mock_session, "expire_all") or isinstance(mock_session.expire_all, AsyncMock):
        mock_session.expire_all = MagicMock()
    if not hasattr(mock_session, "add") or isinstance(mock_session.add, AsyncMock):
        mock_session.add = MagicMock()

    if mock_session.execute.side_effect is None:
        def _sync_execute(statement, *args, **kwargs):
            s = str(statement).lower()
            if "from jobs" in s or "jobs." in s:
                current_ret = mock_session.execute.return_value
                if current_ret is not None and hasattr(current_ret, "scalar_one_or_none"):
                    val = current_ret.scalar_one_or_none.return_value
                    if isinstance(val, Document):
                        job_mock = MagicMock()
                        job_mock.scalar_one_or_none.return_value = val.jobs[0] if (hasattr(val, "jobs") and val.jobs) else None
                        return job_mock
            return mock_session.execute.return_value

        mock_session.execute.side_effect = _sync_execute

    async def _override():
        yield mock_session

    app.dependency_overrides[get_async_session] = _override


@pytest.fixture(autouse=True)
def _setup_and_clear_overrides():
    app.dependency_overrides[get_storage_provider] = lambda: InMemoryStorageProvider()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_concurrent_document_upload_race_condition():
    mock_session = AsyncMock()

    pet = Pet(name="Hank", owner_name="John Bergeson")
    pet.id = 1
    pet.created_at = datetime.now(timezone.utc)

    uploaded_hashes = set()

    async def dynamic_execute(statement, *args, **kwargs):
        mock_result = MagicMock()
        statement_str = str(statement)

        if "FROM pets" in statement_str:
            mock_result.scalar_one_or_none.return_value = pet
            return mock_result

        if "FROM documents" in statement_str:
            mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_result.scalar_one_or_none.return_value = None
        return mock_result

    mock_session.execute.side_effect = dynamic_execute

    async def dynamic_flush():
        file_hash = "mock_hash_constant"
        if file_hash in uploaded_hashes:
            from sqlalchemy.exc import IntegrityError
            raise IntegrityError(
                "duplicate",
                {},
                Exception("duplicate key value violates unique constraint"),
            )
        uploaded_hashes.add(file_hash)

    mock_session.flush = dynamic_flush
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    async def fake_refresh(instance):
        if isinstance(instance, Document):
            instance.id = 10
            instance.created_at = datetime.now(timezone.utc)
        elif isinstance(instance, Job):
            instance.id = 55
            instance.created_at = datetime.now(timezone.utc)

    mock_session.refresh.side_effect = fake_refresh
    _override_session(mock_session)

    file_bytes = b"Shared concurrent document bytes for pet Hank"

    async def upload_task(client_instance: AsyncClient):
        return await client_instance.post(
            "/pets/1/documents",
            files={"file": ("record.pdf", io.BytesIO(file_bytes), "application/pdf")},
        )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        responses = await asyncio.gather(
            upload_task(client),
            upload_task(client),
            upload_task(client),
            upload_task(client),
            upload_task(client),
            return_exceptions=False,
        )

    status_codes = [resp.status_code for resp in responses]
    assert status_codes.count(202) == 1
    assert status_codes.count(409) == 4


@pytest.mark.asyncio
async def test_concurrent_job_completion_race_condition():
    mock_session = AsyncMock()

    job_success = Job(document_id=1, status=JobStatus.ENQUEUED)
    job_success.id = 55
    job_success.created_at = datetime.now(timezone.utc)

    job_already_done = Job(document_id=1, status=JobStatus.DONE)
    job_already_done.id = 55
    job_already_done.created_at = datetime.now(timezone.utc)
    job_already_done.completed_at = datetime.now(timezone.utc)

    res_1 = MagicMock()
    res_1.scalar_one_or_none.return_value = job_success

    res_2_update_fail = MagicMock()
    res_2_update_fail.scalar_one_or_none.return_value = None

    res_2_select_fallback = MagicMock()
    res_2_select_fallback.scalar_one_or_none.return_value = job_already_done

    mock_session.execute.side_effect = [res_1, res_2_update_fail, res_2_select_fallback]
    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp_1, resp_2 = await asyncio.gather(
            client.post(
                "/internal/jobs/55/complete",
                json={"status": "DONE", "summary": "First worker finished"},
            ),
            client.post(
                "/internal/jobs/55/complete",
                json={"status": "DONE", "summary": "Second duplicate worker"},
            ),
        )

    statuses = [resp_1.status_code, resp_2.status_code]
    assert 200 in statuses
    assert 409 in statuses


@pytest.mark.asyncio
async def test_long_poll_interrupted_by_worker_completion():
    mock_session = AsyncMock()

    doc = Document(
        pet_id=1,
        filename="prontuario.pdf",
        file_path="/storage/prontuario.pdf",
        file_hash="hash123",
    )
    doc.id = 10
    doc.created_at = datetime.now(timezone.utc)

    job = Job(document_id=10, status=JobStatus.ENQUEUED)
    job.id = 55
    job.created_at = datetime.now(timezone.utc)
    doc.jobs = [job]

    async def dynamic_execute(statement, *args, **kwargs):
        statement_str = str(statement).lower()
        mock_result = MagicMock()
        if "jobs" in statement_str and "documents" not in statement_str:
            mock_result.scalar_one_or_none.return_value = job
            return mock_result
        mock_result.scalar_one_or_none.return_value = doc
        return mock_result

    mock_session.execute.side_effect = dynamic_execute
    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        poll_task = asyncio.create_task(
            client.get("/documents/10/poll?timeout=10.0")
        )

        await asyncio.sleep(0.1)

        job.status = JobStatus.DONE
        job.summary = "Processing completed in background while polling"
        job.completed_at = datetime.now(timezone.utc)

        response = await poll_task

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 10
    assert payload["latest_job"]["status"] == "DONE"
    assert payload["latest_job"]["summary"] == "Processing completed in background while polling"


@pytest.mark.asyncio
async def test_long_poll_timeout_returns_204():
    mock_session = AsyncMock()

    doc = Document(
        pet_id=1,
        filename="prontuario.pdf",
        file_path="/storage/prontuario.pdf",
        file_hash="hash123",
    )
    doc.id = 10
    doc.created_at = datetime.now(timezone.utc)

    job = Job(document_id=10, status=JobStatus.ENQUEUED)
    job.id = 55
    job.created_at = datetime.now(timezone.utc)
    doc.jobs = [job]

    async def dynamic_execute(statement, *args, **kwargs):
        statement_str = str(statement).lower()
        mock_result = MagicMock()
        if "jobs" in statement_str and "documents" not in statement_str:
            mock_result.scalar_one_or_none.return_value = job
            return mock_result
        mock_result.scalar_one_or_none.return_value = doc
        return mock_result

    mock_session.execute.side_effect = dynamic_execute
    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/documents/10/poll?timeout=1.0")

    assert response.status_code == 204
    assert response.headers.get("Cache-Control") == "no-cache, no-store, must-revalidate"


@pytest.mark.asyncio
async def test_long_poll_client_disconnect_cancellation():
    mock_session = AsyncMock()
    mock_session.expire_all = MagicMock()
    storage = InMemoryStorageProvider()
    service = DocumentService(session=mock_session, storage=storage)

    doc = Document(
        pet_id=1,
        filename="prontuario.pdf",
        file_path="/storage/prontuario.pdf",
        file_hash="hash123",
    )
    doc.id = 10
    doc.created_at = datetime.now(timezone.utc)

    job = Job(document_id=10, status=JobStatus.ENQUEUED)
    job.id = 55
    job.created_at = datetime.now(timezone.utc)
    doc.jobs = [job]

    async def dynamic_execute(statement, *args, **kwargs):
        statement_str = str(statement).lower()
        mock_result = MagicMock()
        if "jobs" in statement_str and "documents" not in statement_str:
            mock_result.scalar_one_or_none.return_value = job
            return mock_result
        mock_result.scalar_one_or_none.return_value = doc
        return mock_result

    mock_session.execute.side_effect = dynamic_execute

    call_count = 0

    async def mock_is_disconnected():
        nonlocal call_count
        call_count += 1
        return call_count >= 2

    document, latest_job = await service.poll_document_status(
        document_id=10,
        timeout_seconds=25.0,
        poll_interval_seconds=0.01,
        is_disconnected_callable=mock_is_disconnected,
    )

    assert document is None
    assert latest_job is None
    assert call_count >= 2


@pytest.mark.asyncio
async def test_x_request_id_tracing_header():
    mock_session = AsyncMock()
    _override_session(mock_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        resp_generated = await client.get("/health")
        assert resp_generated.status_code == 200
        assert "X-Request-ID" in resp_generated.headers
        assert len(resp_generated.headers["X-Request-ID"]) > 10

        custom_id = "trace-client-12345"
        resp_propagated = await client.get(
            "/health",
            headers={"X-Request-ID": custom_id},
        )
        assert resp_propagated.status_code == 200
        assert resp_propagated.headers["X-Request-ID"] == custom_id
