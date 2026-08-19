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
