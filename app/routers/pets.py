from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.exceptions import PetNotFoundException
from app.schemas.pet import PetCreate, PetResponse
from app.services import pet_service

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post(
    "",
    response_model=PetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new pet",
)
async def create_pet(
    pet_data: PetCreate,
    session: AsyncSession = Depends(get_async_session),
) -> PetResponse:
    pet = await pet_service.create_pet(session, pet_data)
    return PetResponse.model_validate(pet)


@router.get(
    "/{pet_id}",
    response_model=PetResponse,
    status_code=status.HTTP_200_OK,
    summary="Get pet by ID",
)
async def get_pet(
    pet_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> PetResponse:
    pet = await pet_service.get_pet_by_id(session, pet_id)
    if pet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pet with id {pet_id} not found",
        )
    return PetResponse.model_validate(pet)
