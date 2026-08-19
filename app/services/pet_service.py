from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pet import Pet
from app.schemas.pet import PetCreate


async def create_pet(session: AsyncSession, pet_data: PetCreate) -> Pet:
    pet = Pet(name=pet_data.name, owner_name=pet_data.owner_name)
    session.add(pet)
    await session.commit()
    await session.refresh(pet)
    return pet


async def get_pet_by_id(session: AsyncSession, pet_id: int) -> Optional[Pet]:
    result = await session.execute(select(Pet).where(Pet.id == pet_id))
    return result.scalar_one_or_none()
