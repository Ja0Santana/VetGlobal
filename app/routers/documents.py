from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.core.exceptions import (
    DocumentNotFoundException,
    DuplicateDocumentException,
    EmptyFileException,
    FileSizeExceededException,
    InvalidFileExtensionException,
    PetNotFoundException,
)
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentUploadResponse,
    JobSummaryResponse,
)
from app.services.document_service import DocumentService, get_document_service

router = APIRouter(tags=["documents"])


@router.post(
    "/pets/{pet_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for a pet",
)
async def upload_document(
    pet_id: int = Path(..., ge=1, description="Positive integer ID"),
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
) -> DocumentUploadResponse:
    try:
        document, job = await service.upload_document(
            pet_id=pet_id, file=file
        )
    except PetNotFoundException as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    except (InvalidFileExtensionException, EmptyFileException) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except FileSizeExceededException as error:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
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
        status=getattr(job.status, "value", str(job.status)),
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document details and latest summary",
)
async def get_document(
    document_id: int = Path(..., ge=1, description="Positive integer Document ID"),
    service: DocumentService = Depends(get_document_service),
) -> DocumentDetailResponse:
    document, latest_job = await service.get_document_with_latest_job(
        document_id=document_id
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with id {document_id} not found",
        )

    job_summary = None
    if latest_job is not None:
        job_summary = JobSummaryResponse(
            id=latest_job.id,
            status=latest_job.status_value,
            summary=latest_job.summary,
            error_message=latest_job.error_message,
            completed_at=latest_job.completed_at,
        )

    return DocumentDetailResponse(
        id=document.id,
        pet_id=document.pet_id,
        filename=document.filename,
        created_at=document.created_at,
        latest_job=job_summary,
    )


@router.get(
    "/documents/{document_id}/poll",
    response_model=Optional[DocumentDetailResponse],
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Document processing completed (DONE or FAILED)",
            "model": DocumentDetailResponse,
        },
        204: {
            "description": "Polling timeout reached without completion (still ENQUEUED)",
        },
        404: {"description": "Document not found"},
    },
    summary="Long-poll document status until processing completes",
)
async def poll_document(
    request: Request,
    response: Response,
    document_id: int = Path(..., ge=1, description="Positive integer Document ID"),
    after_job_id: int = Query(
        default=0,
        ge=0,
        description="Only return jobs with ID greater than this value (default: 0)",
    ),
    timeout_seconds: float = Query(
        default=25.0,
        alias="timeout",
        ge=1.0,
        le=25.0,
        description="Long-polling timeout in seconds (maximum: 25.0s)",
    ),
    service: DocumentService = Depends(get_document_service),
):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    try:
        document, latest_job = await service.poll_document_status(
            document_id=document_id,
            after_job_id=after_job_id,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=1.0,
            is_disconnected_callable=request.is_disconnected,
        )
    except DocumentNotFoundException as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )

    if document is None or latest_job is None:
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )

    job_summary = JobSummaryResponse(
        id=latest_job.id,
        status=latest_job.status_value,
        summary=latest_job.summary,
        error_message=latest_job.error_message,
        completed_at=latest_job.completed_at,
    )

    return DocumentDetailResponse(
        id=document.id,
        pet_id=document.pet_id,
        filename=document.filename,
        created_at=document.created_at,
        latest_job=job_summary,
    )
