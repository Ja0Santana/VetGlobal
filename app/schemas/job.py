from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.models.job_status import JobStatus


class JobCompleteRequest(BaseModel):
    status: JobStatus
    summary: Optional[str] = None
    error: Optional[str] = None

    @field_validator("summary", "error", mode="before")
    @classmethod
    def sanitize_optional_text(cls, value: object) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Field must be a valid string")
        sanitized_value = value.strip()
        if not sanitized_value:
            raise ValueError("Field cannot be empty or contain only whitespace")
        return sanitized_value

    @model_validator(mode="after")
    def validate_status_payload_consistency(self) -> "JobCompleteRequest":
        if self.status == JobStatus.DONE:
            if not self.summary:
                raise ValueError("Field 'summary' is required when status is 'DONE'")
            self.error = None
        elif self.status == JobStatus.FAILED:
            if not self.error:
                raise ValueError("Field 'error' is required when status is 'FAILED'")
            self.summary = None
        else:
            raise ValueError("Status must be either 'DONE' or 'FAILED'")
        return self


class JobCompleteResponse(BaseModel):
    job_id: int
    document_id: int
    status: str
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)
