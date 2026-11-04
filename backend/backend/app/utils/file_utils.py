import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import magic

from app.config import settings


MIME_TYPE_MAP = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
}


def validate_extension(filename: str) -> Tuple[bool, str]:
    """Validate file extension against allowed list. Returns (is_valid, extension)."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in settings.ALLOWED_EXTENSIONS, ext


def validate_mime_type(file_bytes: bytes, expected_extension: str) -> Tuple[bool, str]:
    """Validate MIME type using python-magic. Returns (is_valid, detected_mime)."""
    detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)

    # For .txt files, python-magic might detect various text subtypes
    if expected_extension == ".txt":
        return detected_mime.startswith("text/"), detected_mime

    expected_mime = MIME_TYPE_MAP.get(expected_extension, "")

    # For .pdf files, python-magic can misdetect some valid PDFs as text/plain
    # (e.g. linearized PDFs, PDFs with long XML preambles, or PDFs whose %PDF
    # header appears beyond the default sniff window). Fall back to checking
    # for the %PDF magic marker anywhere in the first 4096 bytes.
    if expected_extension == ".pdf" and detected_mime != expected_mime:
        header_chunk = file_bytes[:4096]
        if b"%PDF" in header_chunk:
            return True, "application/pdf"

    return detected_mime == expected_mime, detected_mime


def compute_sha256(file_bytes: bytes) -> str:
    """Compute SHA256 hash of file bytes."""
    return hashlib.sha256(file_bytes).hexdigest()


def generate_object_name(sha256_hash: str, extension: str) -> str:
    """
    Generate a storage object name using the file's SHA256 hash.
    The hash makes the name secure (no original filename exposed)
    and unique (content-based naming).
    Returns: e.g. '2026/06/a1b2c3d4e5f6...abc.pdf'
    """
    now = datetime.now(timezone.utc)
    return f"{now.year}/{now.month:02d}/{sha256_hash}{extension}"


def _sanitize_for_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert datetime objects to ISO strings for JSONB storage."""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, datetime):
            sanitized[key] = value.isoformat()
        elif value is None:
            sanitized[key] = None
        else:
            sanitized[key] = str(value) if not isinstance(value, (int, float, bool, list, dict)) else value
    return sanitized


def extract_pdf_metadata(file_bytes: bytes) -> Dict[str, Any]:
    """Extract metadata from a PDF file stream."""
    from PyPDF2 import PdfReader
    import io

    metadata: Dict[str, Any] = {}
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        info = reader.metadata
        metadata["page_count"] = len(reader.pages)

        if info:
            metadata["title"] = getattr(info, "title", None) or info.get("/Title")
            metadata["author"] = getattr(info, "author", None) or info.get("/Author")
            metadata["producer"] = getattr(info, "producer", None) or info.get("/Producer")
            metadata["subject"] = getattr(info, "subject", None) or info.get("/Subject")
            metadata["keywords"] = info.get("/Keywords")
            creation = getattr(info, "creation_date", None)
            modification = getattr(info, "modification_date", None)
            metadata["creation_date"] = creation if isinstance(creation, datetime) else _parse_pdf_date(info.get("/CreationDate"))
            metadata["modification_date"] = modification if isinstance(modification, datetime) else _parse_pdf_date(info.get("/ModDate"))
    except Exception:
        metadata["extraction_error"] = "Failed to extract PDF metadata"

    return metadata


def _parse_pdf_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse PDF date string format D:YYYYMMDDHHmmSS."""
    if not date_str:
        return None
    try:
        date_str = str(date_str)
        # Remove D: prefix if present
        if date_str.startswith("D:"):
            date_str = date_str[2:]
        # Take first 14 chars: YYYYMMDDHHmmSS
        date_str = date_str[:14].ljust(14, "0")
        return datetime.strptime(date_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def extract_docx_metadata(file_bytes: bytes) -> Dict[str, Any]:
    """Extract metadata from a DOCX file stream."""
    from docx import Document
    import io

    metadata: Dict[str, Any] = {}
    try:
        doc = Document(io.BytesIO(file_bytes))
        props = doc.core_properties
        metadata["title"] = props.title
        metadata["author"] = props.author
        metadata["subject"] = props.subject
        metadata["keywords"] = props.keywords
        metadata["creation_date"] = props.created
        metadata["modification_date"] = props.modified
        # Count paragraphs as a proxy (no page count in DOCX without rendering)
        metadata["page_count"] = None
    except Exception:
        metadata["extraction_error"] = "Failed to extract DOCX metadata"

    return metadata


def extract_txt_metadata(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """Extract basic metadata from a TXT file stream."""
    metadata: Dict[str, Any] = {
        "title": filename,
        "page_count": None,
    }
    try:
        content = file_bytes.decode("utf-8", errors="replace")
        line_count = content.count("\n") + 1
        metadata["line_count"] = line_count
    except Exception:
        metadata["extraction_error"] = "Failed to read TXT file"

    return metadata


def extract_metadata(file_bytes: bytes, extension: str, filename: str) -> Dict[str, Any]:
    """Extract metadata based on file type."""
    if extension == ".pdf":
        return extract_pdf_metadata(file_bytes)
    elif extension == ".docx":
        return extract_docx_metadata(file_bytes)
    elif extension == ".txt":
        return extract_txt_metadata(file_bytes, filename)
    return {}

