import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles, get_current_user
from app.models.user import User
from app.schemas.audit import AuditLogOut, AuditLogListOut, DashboardStats
from app.services import audit_service

router = APIRouter(prefix="/api", tags=["Audit Logs"])


@router.get("/audit-logs", response_model=AuditLogListOut)
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    action: str = Query(None),
    user_id: uuid.UUID = Query(None),
    current_user: User = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs with optional filtering (admin only)."""
    logs, total = await audit_service.get_audit_logs(
        db, skip=skip, limit=limit, action=action, user_id=user_id
    )
    return AuditLogListOut(
        logs=[AuditLogOut.from_orm_with_user(log) for log in logs],
        total=total,
    )


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics."""
    stats = await audit_service.get_dashboard_stats(db)
    return DashboardStats(**stats)
