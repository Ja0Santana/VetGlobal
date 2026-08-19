from datetime import datetime
from pydantic import BaseModel, ConfigDict


class PetCreate(BaseModel):
    name: str
    owner_name: str


class PetResponse(BaseModel):
    id: int
    name: str
    owner_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
