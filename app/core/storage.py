import hashlib
import os
from dataclasses import dataclass
from typing import Dict, Protocol
import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import EmptyFileException, FileSizeExceededException

CHUNK_SIZE = 65_536
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


@dataclass(frozen=True)
class StoredFile:
    file_path: str
    filename: str
    file_hash: str
    size_bytes: int


class StorageProvider(Protocol):
    async def save_file(
        self, file: UploadFile, pet_id: int, filename: str
    ) -> StoredFile:
        ...

    async def delete_file(self, file_path: str) -> None:
        ...


class LocalStorageProvider:
    def __init__(self, storage_path: str = settings.STORAGE_PATH):
        self.storage_path = storage_path

    async def save_file(
        self, file: UploadFile, pet_id: int, filename: str
    ) -> StoredFile:
        os.makedirs(self.storage_path, exist_ok=True)

        sha256_hash = hashlib.sha256()
        temp_filename = f"_temp_{pet_id}_{filename}"
        temp_path = os.path.join(self.storage_path, temp_filename)
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
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise EmptyFileException(filename)

            file_hash = sha256_hash.hexdigest()
            final_filename = f"{pet_id}_{file_hash[:12]}_{filename}"
            final_path = os.path.join(self.storage_path, final_filename)

            os.replace(temp_path, final_path)

            return StoredFile(
                file_path=final_path,
                filename=final_filename,
                file_hash=file_hash,
                size_bytes=total_bytes,
            )

        except (EmptyFileException, FileSizeExceededException, Exception):
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

    async def delete_file(self, file_path: str) -> None:
        if os.path.exists(file_path):
            os.remove(file_path)


class InMemoryStorageProvider:
    def __init__(self):
        self.files: Dict[str, bytes] = {}

    async def save_file(
        self, file: UploadFile, pet_id: int, filename: str
    ) -> StoredFile:
        sha256_hash = hashlib.sha256()
        total_bytes = 0
        chunks = []

        while chunk := await file.read(CHUNK_SIZE):
            total_bytes += len(chunk)
            if total_bytes > MAX_FILE_SIZE_BYTES:
                raise FileSizeExceededException(MAX_FILE_SIZE_MB)
            sha256_hash.update(chunk)
            chunks.append(chunk)

        if total_bytes == 0:
            raise EmptyFileException(filename)

        file_hash = sha256_hash.hexdigest()
        final_filename = f"{pet_id}_{file_hash[:12]}_{filename}"
        in_memory_path = f"memory://{final_filename}"
        self.files[in_memory_path] = b"".join(chunks)

        return StoredFile(
            file_path=in_memory_path,
            filename=final_filename,
            file_hash=file_hash,
            size_bytes=total_bytes,
        )

    async def delete_file(self, file_path: str) -> None:
        self.files.pop(file_path, None)


def get_storage_provider() -> StorageProvider:
    return LocalStorageProvider(storage_path=settings.STORAGE_PATH)
