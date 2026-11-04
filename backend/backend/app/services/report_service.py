import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload, defer

from app.models.report import Report, ReportMetadata, FileValidation, FileStorage, UploadStatus, PartialDuplicate, ReportsData
from app.models.audit import AuditLog
from app.utils.file_utils import (
    validate_extension,
    validate_mime_type,
    compute_sha256,
    generate_object_name,
    extract_metadata,
    _sanitize_for_json,
    MIME_TYPE_MAP,
)
from app.utils.seaweedfs_utils import upload_file, delete_file
from app.utils.clamav_utils import scan_file_bytes
from app.utils.simhash_utils import calculate_simhash, is_partial_duplicate


async def upload_report(
    db: AsyncSession,
    file_bytes: bytes,
    filename: str,
    user_id: uuid.UUID,
    agency_id: Optional[uuid.UUID] = None,
) -> Dict[str, Any]:
    """
    Full upload workflow:
    1. Validate extension
    2. Validate MIME type
    3. Check SHA256 duplicate
    4. Save to disk
    5. Extract metadata
    6. Create DB records
    7. Create audit log
    """
    # 1. Validate extension
    ext_valid, extension = validate_extension(filename)
    if not ext_valid:
        # Create audit log for rejection
        await _create_audit_log(
            db, user_id, None, "FILE_UPLOAD", "FAILED",
            {"reason": f"Invalid file extension: {extension}", "filename": filename}
        )
        raise ValueError(f"File extension '{extension}' is not allowed. Allowed: .pdf, .docx, .txt")

    # 2. Validate MIME type
    mime_valid, detected_mime = validate_mime_type(file_bytes, extension)
    
    # Auto-correct extension if the user uploaded a valid file type with the wrong extension
    if not mime_valid:
        if detected_mime.startswith("text/"):
            extension = ".txt"
            mime_valid = True
        elif detected_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or (detected_mime == "application/zip" and b"word/document.xml" in file_bytes[:200000]):
            extension = ".docx"
            mime_valid = True
            
    if not mime_valid:
        await _create_audit_log(
            db, user_id, None, "FILE_UPLOAD", "FAILED",
            {"reason": f"MIME type mismatch: {detected_mime}", "filename": filename}
        )
        raise ValueError(
            f"File content type '{detected_mime}' does not match extension '{extension}'"
        )

    # 2.5 Convert to PDF immediately (system only sees PDF from here on)
    from app.utils.pdf_converter import convert_to_pdf
    import os
    try:
        file_bytes = convert_to_pdf(file_bytes, extension, filename)
        extension = ".pdf"
        detected_mime = "application/pdf"
        # Rename filename to .pdf so the DB and UI only see PDF
        base_name = os.path.splitext(filename)[0]
        filename = f"{base_name}.pdf"
    except ValueError as e:
        await _create_audit_log(
            db, user_id, None, "FILE_UPLOAD", "FAILED",
            {"reason": f"PDF conversion failed: {str(e)}", "filename": filename}
        )
        raise ValueError(f"PDF conversion failed: {str(e)}")

    # 3. Compute SHA256 and check duplicates (on the PDF)
    sha256_hash = compute_sha256(file_bytes)
    existing = await db.execute(
        select(Report).where(Report.sha256_hash == sha256_hash)
    )
    if existing.scalar_one_or_none():
        await _create_audit_log(
            db, user_id, None, "FILE_UPLOAD", "FAILED",
            {"reason": "Duplicate file detected", "sha256": sha256_hash, "filename": filename}
        )
        raise ValueError("A file with the same content (SHA256 hash) already exists")

    # 3.5 Malware Scan
    try:
        is_clean, scan_message = await scan_file_bytes(file_bytes)
    except Exception as e:
        await _create_audit_log(
            db, user_id, None, "FILE_UPLOAD", "FAILED",
            {"reason": f"Malware scan failed: {str(e)}", "filename": filename}
        )
        await db.commit()
        raise ValueError(f"Malware scan failed: {str(e)}")

    if not is_clean:
        report = Report(
            uploaded_by=user_id,
            original_filename=filename,
            stored_filename="MALWARE_REJECTED",
            file_extension=extension,
            mime_type=detected_mime,
            file_size=len(file_bytes),
            sha256_hash=sha256_hash,
            page_count=None,
            upload_status=UploadStatus.REJECTED,
        )
        db.add(report)
        await db.flush()

        validation = FileValidation(
            report_id=report.report_id,
            file_type_valid=True,
            malware_scan_status="FAILED",
            duplicate_status="UNIQUE",
            validation_status="FAILED",
            validation_notes=scan_message,
        )
        db.add(validation)
        await db.flush()

        await _create_audit_log(
            db, user_id, report.report_id, "FILE_UPLOAD", "FAILED",
            {"reason": scan_message, "filename": filename}
        )
        await db.commit()
        raise ValueError(scan_message)

    # 3.7 SimHash Partial Duplicate Check
    simhash_val = calculate_simhash(file_bytes, extension)
    duplicate_status = "UNIQUE"
    
    partial_duplicate_info = None

    if simhash_val:
        # Fetch existing simhashes to compare
        # In a real large-scale system, we'd use pg_similarity or bitwise queries, 
        # but for this scale we can fetch them and compare in Python
        existing_reports = await db.execute(
            select(Report.report_id, Report.simhash, Report.original_filename)
            .where(Report.simhash.isnot(None))
            .where(Report.upload_status != UploadStatus.REJECTED)
        )
        for r_id, ex_simhash, ex_filename in existing_reports.all():
            if is_partial_duplicate(simhash_val, ex_simhash):
                duplicate_status = "PARTIAL_DUPLICATE"
                
                # We calculate exact hamming distance for the record (though is_partial_duplicate already does, it returns bool)
                # Let's just store the info so we can create the record later
                def get_hamming_distance(s1, s2):
                    try:
                        x = (int(s1) ^ int(s2)) & ((1 << 64) - 1)
                        ans = 0
                        while x:
                            ans += 1
                            x &= x - 1
                        return ans
                    except: return None
                
                partial_duplicate_info = {
                    "original_report_id": r_id,
                    "original_filename": ex_filename,
                    "hamming_distance": get_hamming_distance(simhash_val, ex_simhash)
                }

                await _create_audit_log(
                    db, user_id, None, "PARTIAL_DUPLICATE_DETECTED", "WARNING",
                    {
                        "filename": filename,
                        "similar_to": ex_filename,
                        "simhash": simhash_val
                    }
                )
                break

    # 4. Extract metadata first (in-memory) from the PDF
    file_metadata = extract_metadata(file_bytes, extension, filename)
    page_count = file_metadata.get("page_count")

    # 5. Encrypt and Upload converted PDF to SeaweedFS
    object_name = generate_object_name(sha256_hash, extension)
    try:
        from app.utils.encryption_utils import encrypt_file
        encrypted_bytes = encrypt_file(file_bytes)
        upload_file(object_name, encrypted_bytes, content_type=detected_mime)
    except Exception as e:
        await _create_audit_log(
            db, user_id, None, "FILE_UPLOAD", "FAILED",
            {"reason": f"Storage upload/encryption failed: {str(e)}", "filename": filename}
        )
        raise ValueError(f"Failed to encrypt and upload file to storage: {str(e)}")

    # 6. Create Report record
    report = Report(
        uploaded_by=user_id,
        original_filename=filename,
        stored_filename=object_name,
        file_extension=extension,
        mime_type=detected_mime,
        file_size=len(file_bytes),
        sha256_hash=sha256_hash,
        simhash=simhash_val,
        page_count=page_count,
        upload_status=UploadStatus.UPLOADED,
        agency_id=agency_id,
    )
    db.add(report)
    await db.flush()

    # Create FileValidation record
    validation = FileValidation(
        report_id=report.report_id,
        file_type_valid=True,
        malware_scan_status="PASSED",
        duplicate_status=duplicate_status,
        validation_status="PASSED",
        validation_notes="Clear from malware",
    )
    db.add(validation)

    # Create ReportMetadata record
    report_meta = ReportMetadata(
        report_id=report.report_id,
        title=file_metadata.get("title"),
        author=file_metadata.get("author"),
        producer=file_metadata.get("producer"),
        subject=file_metadata.get("subject"),
        keywords=file_metadata.get("keywords"),
        creation_date=file_metadata.get("creation_date"),
        modification_date=file_metadata.get("modification_date"),
        metadata_json=_sanitize_for_json(file_metadata),
    )
    db.add(report_meta)

    # Create FileStorage record
    file_storage = FileStorage(
        report_id=report.report_id,
        encrypted_file_path=object_name,
        encryption_algorithm="Fernet",
        encryption_key_id="v1",
        checksum=sha256_hash,
    )
    db.add(file_storage)

    # Update status to VALIDATED
    report.upload_status = UploadStatus.VALIDATED  # type: ignore
    await db.flush()

    # Create PartialDuplicate record if applicable
    if partial_duplicate_info:
        pd_record = PartialDuplicate(
            report_id=report.report_id,
            original_report_id=partial_duplicate_info["original_report_id"],
            original_filename=partial_duplicate_info["original_filename"],
            hamming_distance=partial_duplicate_info["hamming_distance"]
        )
        db.add(pd_record)
        await db.flush()

    # 7. Create audit log
    await _create_audit_log(
        db, user_id, report.report_id, "FILE_UPLOAD", "SUCCESS",  # type: ignore
        {
            "filename": filename,
            "file_size": len(file_bytes),
            "sha256": sha256_hash,
            "mime_type": detected_mime,
        }
    )

    return {
        "report_id": report.report_id,
        "original_filename": filename,
        "upload_status": report.upload_status.value,
        "file_size": len(file_bytes),
        "sha256_hash": sha256_hash,
        "simhash": simhash_val,
        "validation_status": "PASSED",
        "duplicate_status": duplicate_status,
        "message": "File uploaded and validated successfully" if duplicate_status == "UNIQUE" else "File uploaded but flagged as a partial duplicate",
    }


async def get_reports(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
) -> tuple[List[Report], int]:
    """Get paginated list of reports with optional search."""
    query = select(Report).options(
        joinedload(Report.uploader),
        joinedload(Report.agency),
        selectinload(Report.report_metadata),
        selectinload(Report.validation),
        selectinload(Report.partial_duplicate),
        selectinload(Report.storage),
        selectinload(Report.report_data).load_only(ReportsData.report_id),
    )

    if search:
        query = query.where(
            Report.original_filename.ilike(f"%{search}%")
        )

    # Count total
    count_query = select(func.count(Report.report_id))
    if search:
        count_query = count_query.where(
            Report.original_filename.ilike(f"%{search}%")
        )
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Fetch
    result = await db.execute(
        query.order_by(Report.created_at.desc()).offset(skip).limit(limit)
    )
    reports = list(result.scalars().unique().all())
    
    for r in reports:
        r.has_pipeline_data = r.report_data is not None

    return reports, total


async def get_report_by_id(
    db: AsyncSession, report_id: uuid.UUID
) -> Optional[Report]:
    """Get a single report with all related data."""
    result = await db.execute(
        select(Report)
        .options(
            joinedload(Report.uploader),
            joinedload(Report.agency),
            selectinload(Report.report_metadata),
            selectinload(Report.validation),
            selectinload(Report.storage),
            selectinload(Report.partial_duplicate),
            selectinload(Report.report_data).load_only(ReportsData.report_id),
        )
        .where(Report.report_id == report_id)
    )
    report = result.unique().scalar_one_or_none()
    
    if report:
        report.has_pipeline_data = report.report_data is not None
        
    return report


async def delete_report(
    db: AsyncSession, report_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Delete a report permanently from storage and DB."""
    report = await get_report_by_id(db, report_id)
    if not report:
        return False

    # Delete from storage
    if report.storage and report.storage.encrypted_file_path:
        delete_file(report.storage.encrypted_file_path)

    # Delete from database
    await db.delete(report)
    await db.flush()

    await _create_audit_log(
        db, user_id, None, "FILE_DELETE", "SUCCESS",
        {
            "filename": report.original_filename,
            "deleted_report_id": str(report_id)
        }
    )

    return True


async def _create_audit_log(
    db: AsyncSession,
    user_id: uuid.UUID,
    report_id: Optional[uuid.UUID],
    action: str,
    status: str,
    details: Optional[Dict] = None,
):
    """Create an audit log entry."""
    log = AuditLog(
        user_id=user_id,
        report_id=report_id,
        action=action,
        status=status,
        details=details,
    )
    db.add(log)
    await db.flush()
