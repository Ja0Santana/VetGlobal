import asyncio
import os
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, Tuple

from fastapi import Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.exceptions import (
    DocumentNotFoundException,
    DuplicateDocumentException,
    InvalidFileExtensionException,
    PetNotFoundException,
)
from app.core.storage import StorageProvider, get_storage_provider
from app.models.document import Document
from app.models.job import Job
from app.models.job_status import JobStatus
from app.services.pet_service import get_pet_by_id

ALLOWED_EXTENSIONS = [".txt", ".pdf"]


def _sanitize_and_validate_filename(raw_filename: str | None) -> str:
    if raw_filename is None:
        raise InvalidFileExtensionException("unknown", ALLOWED_EXTENSIONS)

    sanitized = os.path.basename(raw_filename).strip()
    if not sanitized:
        raise InvalidFileExtensionException("empty", ALLOWED_EXTENSIONS)

    extension = Path(sanitized).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise InvalidFileExtensionException(sanitized, ALLOWED_EXTENSIONS)

    return sanitized


def _get_current_time() -> float:
    return time.monotonic()


def _is_job_finished(latest_job: Optional[Job], after_job_id: int) -> bool:
    if latest_job is None or latest_job.id <= after_job_id:
        return False
    status_value = getattr(latest_job.status, "value", str(latest_job.status))
    return status_value in (JobStatus.DONE.value, JobStatus.FAILED.value)


async def _has_client_disconnected(
    is_disconnected_callable: Optional[Callable[[], Coroutine[Any, Any, bool]]]
) -> bool:
    if is_disconnected_callable is None:
        return False
    return await is_disconnected_callable()


class DocumentService:
    def __init__(self, session: AsyncSession, storage: StorageProvider):
        self.session = session
        self.storage = storage

    async def upload_document(
        self, pet_id: int, file: UploadFile
    ) -> Tuple[Document, Job]:
        sanitized_filename = _sanitize_and_validate_filename(file.filename)

        pet = await get_pet_by_id(self.session, pet_id)
        if pet is None:
            raise PetNotFoundException(pet_id)

        stored_file = await self.storage.save_file(
            file=file, pet_id=pet_id, filename=sanitized_filename
        )

        existing_document = await self.session.execute(
            select(Document).where(
                Document.pet_id == pet_id,
                Document.file_hash == stored_file.file_hash,
            )
        )
        if existing_document.scalar_one_or_none() is not None:
            await self.storage.delete_file(stored_file.file_path)
            raise DuplicateDocumentException(pet_id, stored_file.file_hash)

        document = Document(
            pet_id=pet_id,
            filename=sanitized_filename,
            file_path=stored_file.file_path,
            file_hash=stored_file.file_hash,
        )
        self.session.add(document)

        try:
            await self.session.flush()
            job = Job(document_id=document.id, status=JobStatus.ENQUEUED)
            self.session.add(job)
            await self.session.commit()
            await self.session.refresh(document)
            await self.session.refresh(job)
            return document, job
        except IntegrityError:
            await self.session.rollback()
            await self.storage.delete_file(stored_file.file_path)
            raise DuplicateDocumentException(pet_id, stored_file.file_hash)
        except Exception:
            await self.session.rollback()
            await self.storage.delete_file(stored_file.file_path)
            raise

    async def get_document_with_latest_job(
        self, document_id: int
    ) -> Tuple[Optional[Document], Optional[Job]]:
        document_query = (
            select(Document)
            .options(selectinload(Document.jobs))
            .where(Document.id == document_id)
        )
        document_result = await self.session.execute(document_query)
        document = document_result.scalar_one_or_none()

        if document is None:
            return None, None

        if hasattr(document, "jobs") and document.jobs is not None:
            if len(document.jobs) > 0:
                latest_job = max(document.jobs, key=lambda item: (item.created_at, item.id))
                return document, latest_job
            return document, None

        job_query = (
            select(Job)
            .where(Job.document_id == document_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(1)
        )
        job_result = await self.session.execute(job_query)
        latest_job = job_result.scalar_one_or_none()

        return document, latest_job

    async def _safely_rollback_session(self) -> None:
        try:
            await self.session.rollback()
        except Exception:
            pass

    async def poll_document_status(
        self,
        document_id: int,
        after_job_id: int = 0,
        timeout_seconds: float = 25.0,
        poll_interval_seconds: float = 1.0,
        is_disconnected_callable: Optional[Callable[[], Coroutine[Any, Any, bool]]] = None,
    ) -> Tuple[Optional[Document], Optional[Job]]:
        start_time = _get_current_time()

        while True:
            if await _has_client_disconnected(is_disconnected_callable):
                return None, None

            self.session.expire_all()
            document, latest_job = await self.get_document_with_latest_job(document_id)

            if document is None:
                raise DocumentNotFoundException(document_id)

            if _is_job_finished(latest_job, after_job_id):
                return document, latest_job

            await self._safely_rollback_session()

            elapsed_time = _get_current_time() - start_time
            if elapsed_time >= timeout_seconds:
                return None, None

            sleep_duration = min(poll_interval_seconds, timeout_seconds - elapsed_time)
            await asyncio.sleep(sleep_duration)


def get_document_service(
    session: AsyncSession = Depends(get_async_session),
    storage: StorageProvider = Depends(get_storage_provider),
) -> DocumentService:
    return DocumentService(session=session, storage=storage)
