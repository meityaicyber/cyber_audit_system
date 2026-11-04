import uuid
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit import AuditLog
from app.models.report import Report
from app.models.user import User


async def get_audit_logs(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
) -> tuple[List[AuditLog], int]:
    """Get paginated list of audit logs with optional filtering."""
    query = select(AuditLog).options(selectinload(AuditLog.user))
    count_query = select(func.count(AuditLog.log_id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)

    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    result = await db.execute(
        query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    )
    logs = result.scalars().unique().all()

    return logs, total


async def get_dashboard_stats(db: AsyncSession) -> dict:
    """Get dashboard statistics."""
    # Total reports
    reports_count = await db.execute(select(func.count(Report.report_id)))
    total_reports = reports_count.scalar()

    # Total users
    users_count = await db.execute(select(func.count(User.user_id)))
    total_users = users_count.scalar()

    # Reports by status
    from app.models.report import UploadStatus
    status_counts = {}
    for status in UploadStatus:
        count_result = await db.execute(
            select(func.count(Report.report_id)).where(
                Report.upload_status == status
            )
        )
        status_counts[status.value] = count_result.scalar()

    # Recent uploads (last 10)
    recent_result = await db.execute(
        select(Report)
        .order_by(Report.created_at.desc())
        .limit(10)
    )
    recent = recent_result.scalars().all()
    recent_uploads = [
        {
            "report_id": str(r.report_id),
            "original_filename": r.original_filename,
            "file_size": r.file_size,
            "upload_status": r.upload_status.value if hasattr(r.upload_status, 'value') else r.upload_status,
            "created_at": r.created_at.isoformat(),
        }
        for r in recent
    ]

    return {
        "total_reports": total_reports,
        "total_users": total_users,
        "recent_uploads": recent_uploads,
        "reports_by_status": status_counts,
    }
