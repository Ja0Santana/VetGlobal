from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.exceptions import (
    DuplicateDocumentException,
    EmptyFileException,
    InvalidFileExtensionException,
    PetNotFoundException,
)
from app.schemas.document import DocumentUploadResponse
from app.services import document_service

router = APIRouter(tags=["documents"])


@router.post(
    "/pets/{pet_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for a pet",
)
async def upload_document(
    pet_id: int,
    file: UploadFile,
    session: AsyncSession = Depends(get_async_session),
) -> DocumentUploadResponse:
    try:
        document, job = await document_service.upload_document(
            session, pet_id, file
        )
    except PetNotFoundException as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    except InvalidFileExtensionException as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except EmptyFileException as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except DuplicateDocumentException as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    return DocumentUploadResponse(
        document_id=document.id,
        job_id=job.id,
        status=job.status.value,
    )
