class PetNotFoundException(Exception):
    def __init__(self, pet_id: int):
        self.pet_id = pet_id
        super().__init__(f"Pet with id {pet_id} not found")


class InvalidFileExtensionException(Exception):
    def __init__(self, filename: str, allowed_extensions: list[str]):
        self.filename = filename
        self.allowed_extensions = allowed_extensions
        super().__init__(
            f"File '{filename}' has unsupported extension. "
            f"Allowed: {', '.join(allowed_extensions)}"
        )


class EmptyFileException(Exception):
    def __init__(self, filename: str):
        self.filename = filename
        super().__init__(f"File '{filename}' is empty")


class DuplicateDocumentException(Exception):
    def __init__(self, pet_id: int, file_hash: str):
        self.pet_id = pet_id
        self.file_hash = file_hash
        super().__init__(
            f"Document with hash '{file_hash[:12]}' already exists for pet {pet_id}"
        )


class FileSizeExceededException(Exception):
    def __init__(self, max_size_mb: int):
        self.max_size_mb = max_size_mb
        super().__init__(f"File size exceeds maximum allowed limit of {max_size_mb}MB")


class JobNotFoundException(Exception):
    def __init__(self, job_id: int):
        self.job_id = job_id
        super().__init__(f"Job with id {job_id} not found")


class JobAlreadyCompletedException(Exception):
    def __init__(self, job_id: int, current_status: str):
        self.job_id = job_id
        self.current_status = current_status
        super().__init__(
            f"Job {job_id} is already completed with status '{current_status}'"
        )


class DocumentNotFoundException(Exception):
    def __init__(self, document_id: int):
        self.document_id = document_id
        super().__init__(f"Document with id {document_id} not found")


