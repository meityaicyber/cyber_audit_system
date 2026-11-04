from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime
from uuid import UUID

from app.schemas.agency import AgencyOut

class ReportMetadataOut(BaseModel):
    metadata_id: UUID
    title: Optional[str] = None
    author: Optional[str] = None
    producer: Optional[str] = None
    subject: Optional[str] = None
    keywords: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    metadata_json: Optional[Dict[str, Any]] = None
    extracted_at: datetime

    model_config = {"from_attributes": True}


class FileValidationOut(BaseModel):
    validation_id: UUID
    file_type_valid: bool
    malware_scan_status: str
    duplicate_status: str
    validation_status: str
    validation_notes: Optional[str] = None
    validated_at: datetime

    model_config = {"from_attributes": True}


class PartialDuplicateOut(BaseModel):
    duplicate_id: UUID
    original_report_id: Optional[UUID] = None
    original_filename: Optional[str] = None
    hamming_distance: Optional[int] = None
    detected_at: datetime

    model_config = {"from_attributes": True}


class FileStorageOut(BaseModel):
    storage_id: UUID
    encrypted_file_path: str
    encryption_algorithm: Optional[str] = None
    encryption_key_id: Optional[str] = None
    stored_at: datetime

    model_config = {"from_attributes": True}

class ReportOut(BaseModel):
    report_id: UUID
    uploaded_by: Optional[UUID] = None
    uploader_username: Optional[str] = None
    original_filename: str
    stored_filename: str
    file_extension: str
    mime_type: str
    file_size: int
    sha256_hash: str
    simhash: Optional[str] = None
    page_count: Optional[int] = None
    upload_status: str
    created_at: datetime
    updated_at: datetime
    metadata: Optional[ReportMetadataOut] = None
    validation: Optional[FileValidationOut] = None
    partial_duplicate: Optional[PartialDuplicateOut] = None
    storage: Optional[FileStorageOut] = None
    agency: Optional[AgencyOut] = None
    has_pipeline_data: bool = False

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_uploader(cls, report):
        uploader_name = report.uploader.username if report.uploader else None
        
        # Check if report_data exists (might be loaded or need a lazy check, but we can do it via a count or if it's joined)
        # However, to be safe, we rely on the service to populate an attribute or we just check if report_data is not None
        # We will add an attribute `has_pipeline_data` to the report object in the service
        _has_data = getattr(report, 'has_pipeline_data', False)
        
        return cls(
            report_id=report.report_id,
            uploaded_by=report.uploaded_by,
            uploader_username=uploader_name,
            original_filename=report.original_filename,
            stored_filename=report.stored_filename,
            file_extension=report.file_extension,
            mime_type=report.mime_type,
            file_size=report.file_size,
            sha256_hash=report.sha256_hash,
            simhash=report.simhash,
            page_count=report.page_count,
            upload_status=report.upload_status.value if hasattr(report.upload_status, 'value') else report.upload_status,
            created_at=report.created_at,
            updated_at=report.updated_at,
            metadata=report.report_metadata,
            validation=report.validation,
            partial_duplicate=report.partial_duplicate,
            storage=report.storage,
            agency=report.agency,
            has_pipeline_data=_has_data,
        )


class ReportListOut(BaseModel):
    reports: List[ReportOut]
    total: int


class UploadResponse(BaseModel):
    report_id: UUID
    original_filename: str
    upload_status: str
    file_size: int
    sha256_hash: str
    simhash: Optional[str] = None
    validation_status: str
    duplicate_status: str
    message: str
    decrypted: Optional[bool] = False
