from datetime import datetime, timezone
from fastapi import APIRouter, Body, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_async_session
from app.core.exceptions import (
    JobAlreadyCompletedException,
    JobNotFoundException,
)
from app.schemas.job import JobCompleteRequest, JobCompleteResponse
from app.services import job_service

router = APIRouter(prefix="/internal", tags=["internal"])


@router.post(
    "/jobs/{job_id}/complete",
    response_model=JobCompleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete a job (Worker simulation callback)",
)
async def complete_job_callback(
    job_id: int = Path(..., ge=1, description="Positive integer Job ID"),
    payload: JobCompleteRequest = Body(...),
    session: AsyncSession = Depends(get_async_session),
) -> JobCompleteResponse:
    try:
        job = await job_service.complete_job(session, job_id, payload)
    except JobNotFoundException as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        )
    except JobAlreadyCompletedException as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    completed_at = job.completed_at or datetime.now(timezone.utc)
    return JobCompleteResponse(
        job_id=job.id,
        document_id=job.document_id,
        status=job.status_value,
        completed_at=completed_at,
    )
