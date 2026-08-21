from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    JobAlreadyCompletedException,
    JobNotFoundException,
)
from app.models.job import Job
from app.models.job_status import JobStatus
from app.schemas.job import (
    JobCompleteRequest,
    JobSuccessRequest,
)


async def complete_job(
    session: AsyncSession,
    job_id: int,
    payload: JobCompleteRequest,
) -> Job:
    summary_value = payload.summary if isinstance(payload, JobSuccessRequest) else None
    error_value = None if isinstance(payload, JobSuccessRequest) else payload.error
    now = datetime.now(timezone.utc)

    update_stmt = (
        update(Job)
        .where(Job.id == job_id, Job.status == JobStatus.ENQUEUED)
        .values(
            status=payload.status,
            summary=summary_value,
            error_message=error_value,
            completed_at=now,
        )
        .returning(Job)
    )
    result = await session.execute(update_stmt)
    updated_job = result.scalar_one_or_none()

    if updated_job is None:
        check_result = await session.execute(select(Job).where(Job.id == job_id))
        existing_job = check_result.scalar_one_or_none()

        if existing_job is None:
            raise JobNotFoundException(job_id)

        current_status = getattr(
            existing_job.status, "value", str(existing_job.status)
        )
        raise JobAlreadyCompletedException(job_id, current_status)

    updated_job.status = payload.status
    updated_job.summary = summary_value
    updated_job.error_message = error_value
    if updated_job.started_at is None:
        updated_job.started_at = updated_job.created_at or now
    updated_job.completed_at = now

    await session.commit()
    return updated_job
