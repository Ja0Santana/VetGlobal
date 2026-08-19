from datetime import datetime
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.job_status import JobStatus


class JobSuccessRequest(BaseModel):
    status: Literal[JobStatus.DONE] = JobStatus.DONE
    summary: str = Field(..., description="Clinical summary of the document")

    @field_validator("summary", mode="before")
    @classmethod
    def sanitize_summary(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Field 'summary' must be a valid string")
        sanitized_value = value.strip()
        if not sanitized_value:
            raise ValueError("Field 'summary' cannot be empty or contain only whitespace")
        return sanitized_value


class JobFailureRequest(BaseModel):
    status: Literal[JobStatus.FAILED] = JobStatus.FAILED
    error: str = Field(..., description="Error message explaining the failure")

    @field_validator("error", mode="before")
    @classmethod
    def sanitize_error(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Field 'error' must be a valid string")
        sanitized_value = value.strip()
        if not sanitized_value:
            raise ValueError("Field 'error' cannot be empty or contain only whitespace")
        return sanitized_value


JobCompleteRequest = Annotated[
    Union[JobSuccessRequest, JobFailureRequest],
    Field(discriminator="status"),
]


class JobCompleteResponse(BaseModel):
    job_id: int
    document_id: int
    status: str
    completed_at: datetime

    model_config = ConfigDict(from_attributes=True)

