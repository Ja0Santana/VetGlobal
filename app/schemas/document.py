from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DocumentUploadResponse(BaseModel):
    document_id: int
    job_id: int
    status: str


class JobSummaryResponse(BaseModel):
    id: int
    status: str
    summary: Optional[str] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailResponse(BaseModel):
    id: int
    pet_id: int
    filename: str
    created_at: datetime
    latest_job: Optional[JobSummaryResponse] = None

    model_config = ConfigDict(from_attributes=True)

