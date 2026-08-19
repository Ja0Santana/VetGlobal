from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PetCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    owner_name: Annotated[str, Field(min_length=1, max_length=255)]

    @field_validator("name", "owner_name", mode="before")
    @classmethod
    def sanitize_and_validate_non_empty_string(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("Field must be a valid string")
        sanitized_value = value.strip()
        if not sanitized_value:
            raise ValueError("Field cannot be empty or contain only whitespace")
        return sanitized_value


class PetResponse(BaseModel):
    id: int
    name: str
    owner_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
