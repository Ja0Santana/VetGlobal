from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    JobAlreadyCompletedException,
    JobNotFoundException,
)
from app.models.job import Job
from app.models.job_status import JobStatus
from app.schemas.job import (
    JobCompleteRequest,
    JobFailureRequest,
    JobSuccessRequest,
)


async def complete_job(
    session: AsyncSession,
    job_id: int,
    payload: JobCompleteRequest,
) -> Job:
    result = await session.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise JobNotFoundException(job_id)

    current_status = getattr(job.status, "value", str(job.status))
    if current_status != JobStatus.ENQUEUED.value:
        raise JobAlreadyCompletedException(job_id, current_status)

    job.status = payload.status
    if isinstance(payload, JobSuccessRequest):
        job.summary = payload.summary
        job.error_message = None
    else:
        job.error_message = payload.error
        job.summary = None

    if job.started_at is None:
        job.started_at = job.created_at or datetime.now(timezone.utc)
    job.completed_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(job)

    return job
