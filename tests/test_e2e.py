from datetime import datetime, timezone
import io
from unittest.mock import AsyncMock, MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_async_session
from app.main import app
from app.models.document import Document
from app.models.job import Job
from app.models.job_status import JobStatus
from app.models.pet import Pet


def _override_session(mock_session):
    if not hasattr(mock_session, "expire_all") or isinstance(
        mock_session.expire_all, AsyncMock
    ):
        mock_session.expire_all = MagicMock()
    if not hasattr(mock_session, "add") or isinstance(
        mock_session.add, AsyncMock
    ):
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
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_complete_e2e_successful_flow():
    mock_session = AsyncMock()
    _override_session(mock_session)

    pet = Pet(name="Rex", owner_name="Carlos")
    pet.id = 1
    pet.created_at = datetime.now(timezone.utc)

    doc = Document(
        pet_id=1,
        filename="prontuario.pdf",
        file_path="/storage/prontuario.pdf",
        file_hash="e2e_hash_123",
    )
    doc.id = 10
    doc.created_at = datetime.now(timezone.utc)

    job = Job(document_id=10, status=JobStatus.ENQUEUED)
    job.id = 55
    job.created_at = datetime.now(timezone.utc)
    doc.jobs = [job]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Step 1: Healthcheck
        mock_session.execute.return_value = MagicMock()
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "healthy"

        # Step 2: Create Pet
        async def fake_refresh_pet(instance):
            instance.id = 1
            instance.created_at = datetime.now(timezone.utc)

        mock_session.refresh.side_effect = fake_refresh_pet
        pet_resp = await client.post(
            "/pets",
            json={"name": "Rex", "owner_name": "Carlos"},
        )
        assert pet_resp.status_code == 201
        assert pet_resp.json()["id"] == 1

        # Step 3: Upload Document
        mock_pet_result = MagicMock()
        mock_pet_result.scalar_one_or_none.return_value = pet
        mock_dup_result = MagicMock()
        mock_dup_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [mock_pet_result, mock_dup_result]

        async def fake_refresh_upload(instance):
            if isinstance(instance, Document):
                instance.id = 10
                instance.created_at = datetime.now(timezone.utc)
            elif isinstance(instance, Job):
                instance.id = 55
                instance.created_at = datetime.now(timezone.utc)

        mock_session.refresh.side_effect = fake_refresh_upload

        fake_file_content = b"%PDF-1.4 sample content for e2e test"
        upload_resp = await client.post(
            "/pets/1/documents",
            files={"file": ("prontuario.pdf", io.BytesIO(fake_file_content), "application/pdf")},
        )
        assert upload_resp.status_code == 202
        upload_data = upload_resp.json()
        assert upload_data["document_id"] == 10
        assert upload_data["job_id"] == 55
        assert upload_data["status"] == "ENQUEUED"

        # Step 4: Query Document Detail (Before Worker Completes)
        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = doc
        mock_session.execute.side_effect = None
        mock_session.execute.return_value = mock_doc_result
        mock_session._smart_wrapped = False
        _override_session(mock_session)

        doc_resp = await client.get("/documents/10")
        assert doc_resp.status_code == 200
        doc_data = doc_resp.json()
        assert doc_data["id"] == 10
        assert doc_data["latest_job"]["status"] == "ENQUEUED"
        assert doc_data["latest_job"]["summary"] is None

        # Step 5: Worker Completes Job (Simulate Worker Callback)
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job
        mock_session.execute.return_value = mock_job_result

        callback_resp = await client.post(
            "/internal/jobs/55/complete",
            json={
                "status": "DONE",
                "summary": "Patient diagnosed with gastritis, treated with omeprazole.",
            },
        )
        assert callback_resp.status_code == 200
        callback_data = callback_resp.json()
        assert callback_data["job_id"] == 55
        assert callback_data["document_id"] == 10
        assert callback_data["status"] == "DONE"

        # Step 6: Long Polling returns 200 OK with Completed Summary
        job.status = JobStatus.DONE
        job.summary = "Patient diagnosed with gastritis, treated with omeprazole."
        job.completed_at = datetime.now(timezone.utc)
        mock_session.execute.side_effect = None
        mock_session.execute.return_value = mock_doc_result
        mock_session._smart_wrapped = False
        _override_session(mock_session)

        poll_resp = await client.get("/documents/10/poll")
        assert poll_resp.status_code == 200
        poll_data = poll_resp.json()
        assert poll_data["id"] == 10
        assert poll_data["latest_job"]["status"] == "DONE"
        assert "gastritis" in poll_data["latest_job"]["summary"]

        # Step 7: Worker Idempotency Check (Second callback on same job rejected)
        mock_none_res = MagicMock()
        mock_none_res.scalar_one_or_none.return_value = None
        mock_job_res = MagicMock()
        mock_job_res.scalar_one_or_none.return_value = job

        mock_session.execute.side_effect = [mock_none_res, mock_job_res]
        recomplete_resp = await client.post(
            "/internal/jobs/55/complete",
            json={
                "status": "DONE",
                "summary": "Duplicate completion attempt.",
            },
        )
        assert recomplete_resp.status_code == 409
        assert "already completed" in recomplete_resp.json()["detail"]


@pytest.mark.asyncio
async def test_e2e_failed_job_flow():
    mock_session = AsyncMock()
    _override_session(mock_session)

    doc = Document(
        pet_id=1,
        filename="corrupted.pdf",
        file_path="/storage/corrupted.pdf",
        file_hash="corrupted_hash",
    )
    doc.id = 20
    doc.created_at = datetime.now(timezone.utc)

    job = Job(document_id=20, status=JobStatus.ENQUEUED)
    job.id = 88
    job.created_at = datetime.now(timezone.utc)
    doc.jobs = [job]

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        # Step 1: Worker Callback Reports Failure
        mock_job_result = MagicMock()
        mock_job_result.scalar_one_or_none.return_value = job
        mock_session.execute.return_value = mock_job_result

        callback_resp = await client.post(
            "/internal/jobs/88/complete",
            json={
                "status": "FAILED",
                "error": "OCR extraction failed: corrupted PDF stream.",
            },
        )
        assert callback_resp.status_code == 200
        assert callback_resp.json()["status"] == "FAILED"

        # Step 2: Long Polling delivers the Failure message to the client
        job.status = JobStatus.FAILED
        job.error_message = "OCR extraction failed: corrupted PDF stream."
        job.completed_at = datetime.now(timezone.utc)

        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = doc
        mock_session.execute.side_effect = None
        mock_session.execute.return_value = mock_doc_result
        mock_session._smart_wrapped = False
        _override_session(mock_session)

        poll_resp = await client.get("/documents/20/poll")
        assert poll_resp.status_code == 200
        poll_data = poll_resp.json()
        assert poll_data["id"] == 20
        assert poll_data["latest_job"]["status"] == "FAILED"
        assert "OCR extraction failed" in poll_data["latest_job"]["error_message"]
