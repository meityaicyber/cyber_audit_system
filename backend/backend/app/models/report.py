import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, BigInteger, Integer, Text, Enum, Date, SmallInteger, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import enum

from app.database import Base


class UploadStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"


class Report(Base):
    __tablename__ = "reports"

    report_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uploaded_by = Column(
        UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    original_filename = Column(String(500), nullable=False)
    stored_filename = Column(String(500), nullable=False)
    file_extension = Column(String(20), nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    simhash = Column(String(64), nullable=True, index=True)
    page_count = Column(Integer, nullable=True)
    upload_status = Column(
        Enum(UploadStatus, name="upload_status_enum", create_constraint=True),
        default=UploadStatus.UPLOADED,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    agency_id = Column(
        UUID(as_uuid=True), ForeignKey("agencies.agency_id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    uploader = relationship("User", back_populates="reports", lazy="joined")
    agency = relationship("Agency", back_populates="reports", lazy="joined")
    report_metadata = relationship(
        "ReportMetadata", back_populates="report", uselist=False, lazy="joined",
        cascade="all, delete-orphan"
    )
    validation = relationship(
        "FileValidation", back_populates="report", uselist=False, lazy="joined",
        cascade="all, delete-orphan"
    )
    storage = relationship(
        "FileStorage", back_populates="report", uselist=False, lazy="joined",
        cascade="all, delete-orphan"
    )
    partial_duplicate = relationship(
        "PartialDuplicate", foreign_keys="PartialDuplicate.report_id", back_populates="report", uselist=False, lazy="joined",
        cascade="all, delete-orphan"
    )
    audit_logs = relationship("AuditLog", back_populates="report", lazy="noload")
    report_data = relationship(
        "ReportsData", back_populates="report", uselist=False, lazy="noload",
        cascade="all, delete-orphan"
    )
    detailed_observations = relationship(
        "DetailedObservation", back_populates="report", lazy="noload",
        cascade="all, delete-orphan"
    )


class ReportMetadata(Base):
    __tablename__ = "report_metadata"

    metadata_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    title = Column(String(500), nullable=True)
    author = Column(String(255), nullable=True)
    producer = Column(String(255), nullable=True)
    subject = Column(Text, nullable=True)
    keywords = Column(Text, nullable=True)
    creation_date = Column(DateTime(timezone=True), nullable=True)
    modification_date = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    extracted_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    report = relationship("Report", back_populates="report_metadata")


class FileValidation(Base):
    __tablename__ = "file_validation"

    validation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    file_type_valid = Column(Boolean, default=False, nullable=False)
    malware_scan_status = Column(String(50), default="SKIPPED", nullable=False)
    duplicate_status = Column(String(50), default="UNIQUE", nullable=False)
    validation_status = Column(String(50), default="PENDING", nullable=False)
    validation_notes = Column(Text, nullable=True)
    validated_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    report = relationship("Report", back_populates="validation")


class FileStorage(Base):
    __tablename__ = "file_storage"

    storage_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    encrypted_file_path = Column(String(1000), nullable=False)
    encryption_algorithm = Column(String(50), nullable=True)
    encryption_key_id = Column(String(255), nullable=True)
    checksum = Column(String(64), nullable=True)
    stored_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    report = relationship("Report", back_populates="storage")


class PartialDuplicate(Base):
    __tablename__ = "partial_duplicates"

    duplicate_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    original_report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="SET NULL"),
        nullable=True,
    )
    original_filename = Column(String(500), nullable=True)
    hamming_distance = Column(Integer, nullable=True)
    detected_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    report = relationship("Report", foreign_keys=[report_id], back_populates="partial_duplicate")
    original_report = relationship("Report", foreign_keys=[original_report_id])


class ObservationStatus(str, enum.Enum):
    OPEN = 'Open'
    CLOSED = 'Closed'
    PARTIALLY_REMEDIATED = 'Partially Remediated'

class ObservationSeverity(str, enum.Enum):
    CRITICAL = 'Critical'
    HIGH = 'High'
    MEDIUM = 'Medium'
    LOW = 'Low'

class ObservationImpact(str, enum.Enum):
    MAJOR = 'Major'
    MODERATE = 'Moderate'
    MINOR = 'Minor'

class ObservationLikelihood(str, enum.Enum):
    EASY = 'Easy'
    MODERATE = 'Moderate'
    HARD = 'Hard'

class ObservationNewRepeat(str, enum.Enum):
    NEW = 'New'
    REPEAT = 'Repeat'

class ReportsData(Base):
    __tablename__ = "reports_data"

    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        primary_key=True,
        default=uuid.uuid4
    )
    report_date = Column(Date, nullable=True, index=True)
    data = Column(JSONB, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    report = relationship("Report", back_populates="report_data")

class DetailedObservation(Base):
    __tablename__ = "detailed_observations"

    finding_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title = Column(Text, nullable=True)
    status = Column(
        Enum(ObservationStatus, name="observation_status", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
        index=True
    )
    severity = Column(
        Enum(ObservationSeverity, name="observation_severity", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
        index=True
    )
    impact_level = Column(
        Enum(ObservationImpact, name="observation_impact", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=True
    )
    likelihood_level = Column(
        Enum(ObservationLikelihood, name="observation_likelihood", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=True
    )
    cve_id = Column(ARRAY(Text), nullable=True)
    cvss_score = Column(Numeric(4, 1), nullable=True)
    cvss_vector = Column(Text, nullable=True)
    severity_rationale = Column(Text, nullable=True)
    reported_epss_score = Column(Numeric(5, 4), nullable=True)
    observation_date = Column(Date, nullable=True)
    cwe = Column(ARRAY(Text), nullable=True)
    affected_asset = Column(ARRAY(Text), nullable=True)
    regulatory_references = Column(ARRAY(Text), nullable=True)
    observation_description = Column(Text, nullable=True)
    preconditions = Column(Text, nullable=True)
    proof_of_concept = Column(JSONB, nullable=True)
    impact = Column(Text, nullable=True)
    likely_root_cause = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    reference = Column(Text, nullable=True)
    new_or_repeat = Column(
        Enum(ObservationNewRepeat, name="observation_new_repeat", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=True
    )
    meta_data = Column("meta", JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    report = relationship("Report", back_populates="detailed_observations")


class ReportChunk(Base):
    __tablename__ = "report_chunks"

    chunk_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reports.report_id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    section_id = Column(String(255), nullable=True, index=True)
    chunk = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=True)
    chunk_index = Column(Integer, nullable=True)
    context_prefix = Column(Text, nullable=True)
    finding_id = Column(String(255), nullable=True, index=True)
    token_count = Column(Integer, nullable=True)
    meta_data = Column("meta", JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
