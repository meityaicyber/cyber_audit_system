import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    report_id = Column(
        UUID(as_uuid=True), ForeignKey("reports.report_id", ondelete="SET NULL"), nullable=True
    )
    action = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False)
    details = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="audit_logs", lazy="joined")
    report = relationship("Report", back_populates="audit_logs", lazy="noload")


class SecurityEvent(Base):
    __tablename__ = "security_events"

    event_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    severity = Column(String(20), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    event_metadata = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
