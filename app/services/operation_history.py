from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from app.database.session import create_session_factory
from app.models.operation_job import OperationJob
from app.models.user import User


@dataclass(frozen=True)
class OperationRecord:
    operation_type: str
    status: str
    created_at: datetime
    result_summary: str | None = None
    error_code: str | None = None


async def record_operation(
    telegram_id: int,
    operation_type: str,
    status: str,
    *,
    result_summary: str | None = None,
    error_code: str | None = None,
    safe_parameters: dict | None = None,
) -> bool:
    """Record an operation without including secrets or message contents."""
    factory = create_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        session.add(
            OperationJob(
                user_id=user.id,
                operation_type=operation_type,
                status=status,
                safe_parameters=safe_parameters,
                result_summary=result_summary,
                error_code=error_code,
            )
        )
        await session.commit()
        return True


async def list_operations(telegram_id: int, limit: int = 10) -> list[OperationRecord]:
    safe_limit = max(1, min(limit, 25))
    factory = create_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            return []
        jobs = await session.execute(
            select(OperationJob)
            .where(OperationJob.user_id == user.id)
            .order_by(OperationJob.created_at.desc(), OperationJob.id.desc())
            .limit(safe_limit)
        )
        return [
            OperationRecord(
                operation_type=job.operation_type,
                status=job.status,
                created_at=job.created_at,
                result_summary=job.result_summary,
                error_code=job.error_code,
            )
            for job in jobs.scalars().all()
        ]
