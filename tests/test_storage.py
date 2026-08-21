import io
import os
import pytest
from fastapi import UploadFile

from app.core.exceptions import EmptyFileException, FileSizeExceededException
from app.core.storage import (
    InMemoryStorageProvider,
    LocalStorageProvider,
    StoredFile,
    get_storage_provider,
)


@pytest.mark.asyncio
async def test_in_memory_storage_save_and_delete():
    storage = InMemoryStorageProvider()
    file_content = b"Sample test content"
    upload_file = UploadFile(
        file=io.BytesIO(file_content),
        filename="sample.txt",
    )

    stored_file = await storage.save_file(
        file=upload_file,
        pet_id=1,
        filename="sample.txt",
    )

    assert isinstance(stored_file, StoredFile)
    assert stored_file.filename == f"1_{stored_file.file_hash[:12]}_sample.txt"
    assert stored_file.size_bytes == len(file_content)
    assert stored_file.file_path in storage.files

    await storage.delete_file(stored_file.file_path)
    assert stored_file.file_path not in storage.files


@pytest.mark.asyncio
async def test_in_memory_storage_empty_file_raises():
    storage = InMemoryStorageProvider()
    upload_file = UploadFile(
        file=io.BytesIO(b""),
        filename="empty.txt",
    )

    with pytest.raises(EmptyFileException):
        await storage.save_file(
            file=upload_file,
            pet_id=1,
            filename="empty.txt",
        )


@pytest.mark.asyncio
async def test_in_memory_storage_exceeded_size_raises(monkeypatch):
    storage = InMemoryStorageProvider()
    monkeypatch.setattr("app.core.storage.MAX_FILE_SIZE_BYTES", 10)
    upload_file = UploadFile(
        file=io.BytesIO(b"Large chunk of content exceeding limit"),
        filename="large.txt",
    )

    with pytest.raises(FileSizeExceededException):
        await storage.save_file(
            file=upload_file,
            pet_id=1,
            filename="large.txt",
        )


@pytest.mark.asyncio
async def test_local_storage_save_and_delete(tmp_path):
    storage = LocalStorageProvider(storage_path=str(tmp_path))
    file_content = b"Local file storage test content"
    upload_file = UploadFile(
        file=io.BytesIO(file_content),
        filename="local_test.txt",
    )

    stored_file = await storage.save_file(
        file=upload_file,
        pet_id=2,
        filename="local_test.txt",
    )

    assert os.path.exists(stored_file.file_path)
    assert stored_file.size_bytes == len(file_content)

    await storage.delete_file(stored_file.file_path)
    assert not os.path.exists(stored_file.file_path)


@pytest.mark.asyncio
async def test_local_storage_empty_file_raises(tmp_path):
    storage = LocalStorageProvider(storage_path=str(tmp_path))
    upload_file = UploadFile(
        file=io.BytesIO(b""),
        filename="empty.txt",
    )

    with pytest.raises(EmptyFileException):
        await storage.save_file(
            file=upload_file,
            pet_id=1,
            filename="empty.txt",
        )


@pytest.mark.asyncio
async def test_local_storage_exceeded_size_raises(tmp_path, monkeypatch):
    storage = LocalStorageProvider(storage_path=str(tmp_path))
    monkeypatch.setattr("app.core.storage.MAX_FILE_SIZE_BYTES", 5)
    upload_file = UploadFile(
        file=io.BytesIO(b"Exceeding content"),
        filename="large.txt",
    )

    with pytest.raises(FileSizeExceededException):
        await storage.save_file(
            file=upload_file,
            pet_id=1,
            filename="large.txt",
        )


def test_get_storage_provider_factory():
    provider = get_storage_provider()
    assert isinstance(provider, LocalStorageProvider)
