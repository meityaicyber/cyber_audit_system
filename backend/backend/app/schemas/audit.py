from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime
from uuid import UUID


class AuditLogOut(BaseModel):
    log_id: UUID
    user_id: Optional[UUID] = None
    username: Optional[str] = None
    report_id: Optional[UUID] = None
    action: str
    status: str
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_user(cls, log):
        username = log.user.username if log.user else None
        return cls(
            log_id=log.log_id,
            user_id=log.user_id,
            username=username,
            report_id=log.report_id,
            action=log.action,
            status=log.status,
            details=log.details,
            created_at=log.created_at,
        )


class AuditLogListOut(BaseModel):
    logs: List[AuditLogOut]
    total: int


class DashboardStats(BaseModel):
    total_reports: int
    total_users: int
    recent_uploads: List[Dict[str, Any]]
    reports_by_status: Dict[str, int]
