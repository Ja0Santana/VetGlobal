import hashlib
import os
from pathlib import Path
from typing import Tuple

import aiofiles
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    DuplicateDocumentException,
    EmptyFileException,
    FileSizeExceededException,
    InvalidFileExtensionException,
    PetNotFoundException,
)
from app.models.document import Document
from app.models.job import Job
from app.models.job_status import JobStatus
from app.services.pet_service import get_pet_by_id

ALLOWED_EXTENSIONS = [".txt", ".pdf"]
CHUNK_SIZE = 65_536
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


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


async def _save_file_with_hash(
    file: UploadFile, storage_path: str, pet_id: int, filename: str
) -> Tuple[str, str, str]:
    os.makedirs(storage_path, exist_ok=True)

    sha256_hash = hashlib.sha256()
    temp_filename = f"_temp_{pet_id}_{filename}"
    temp_path = os.path.join(storage_path, temp_filename)
    total_bytes = 0

    try:
        async with aiofiles.open(temp_path, "wb") as destination:
            while chunk := await file.read(CHUNK_SIZE):
                total_bytes += len(chunk)
                if total_bytes > MAX_FILE_SIZE_BYTES:
                    raise FileSizeExceededException(MAX_FILE_SIZE_MB)
                sha256_hash.update(chunk)
                await destination.write(chunk)

        if total_bytes == 0:
            os.remove(temp_path)
            raise EmptyFileException(filename)

        file_hash = sha256_hash.hexdigest()
        final_filename = f"{pet_id}_{file_hash[:12]}_{filename}"
        final_path = os.path.join(storage_path, final_filename)

        os.replace(temp_path, final_path)

        return final_path, final_filename, file_hash

    except (EmptyFileException, FileSizeExceededException, Exception):
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


async def upload_document(
    session: AsyncSession, pet_id: int, file: UploadFile
) -> Tuple[Document, Job]:
    sanitized_filename = _sanitize_and_validate_filename(file.filename)

    pet = await get_pet_by_id(session, pet_id)
    if pet is None:
        raise PetNotFoundException(pet_id)

    file_path, final_filename, file_hash = await _save_file_with_hash(
        file, settings.STORAGE_PATH, pet_id, sanitized_filename
    )

    existing_document = await session.execute(
        select(Document).where(
            Document.pet_id == pet_id,
            Document.file_hash == file_hash,
        )
    )
    if existing_document.scalar_one_or_none() is not None:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise DuplicateDocumentException(pet_id, file_hash)

    document = Document(
        pet_id=pet_id,
        filename=sanitized_filename,
        file_path=file_path,
        file_hash=file_hash,
    )
    session.add(document)

    try:
        await session.flush()
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    job = Job(document_id=document.id, status=JobStatus.ENQUEUED)
    session.add(job)

    await session.commit()
    await session.refresh(document)
    await session.refresh(job)

    return document, job
