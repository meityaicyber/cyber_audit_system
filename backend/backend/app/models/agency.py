import uuid
from datetime import datetime, timezone, date

from sqlalchemy import Column, String, DateTime, Date, Text, Boolean, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class Agency(Base):
    __tablename__ = "agencies"

    agency_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agency_code = Column(String(50), unique=True, nullable=False, index=True)
    agency_name = Column(String(255), nullable=False, index=True)
    agency_type = Column(String(100), nullable=False)
    registration_number = Column(String(100), unique=True, nullable=True)
    cert_in_empanelled = Column(Boolean, nullable=False, default=False)
    empanelment_number = Column(String(100), nullable=True)
    empanelment_expiry = Column(Date, nullable=True)
    
    contact_person = Column(String(255), nullable=False)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=True)
    website = Column(String(255), nullable=True)
    
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=False, default='India')
    pincode = Column(String(20), nullable=True)
    
    status = Column(String(50), nullable=False, default='ACTIVE')
    onboarding_date = Column(Date, nullable=False, default=date.today)
    remarks = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            status.in_(['ACTIVE', 'INACTIVE', 'SUSPENDED', 'BLACKLISTED']),
            name='chk_status'
        ),
        CheckConstraint(
            agency_type.in_([
                'CERT_IN_EMPANELLED',
                'PRIVATE_AUDITOR',
                'INTERNAL_AUDIT_TEAM',
                'GOVERNMENT_AGENCY',
                'THIRD_PARTY_ASSESSOR'
            ]),
            name='chk_agency_type'
        ),
        CheckConstraint(
            "contact_email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name='chk_email'
        ),
    )

    # Relationships
    reports = relationship("Report", back_populates="agency", lazy="noload")
