from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: int
    job_id: int
    status: str
