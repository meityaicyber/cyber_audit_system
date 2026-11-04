"""Shared fixtures. All documents are synthetic; no client data is used in tests."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import List, Optional

import fitz
import pytest
from PIL import Image

REPORT_PAGES = [
    [
        "Acme Payments API Assessment Report",
        "Report Release Date: 16.02.2026",
        "Type of Audit: API Assessment",
        "Type of Audit Report: Follow Up Report",
        "Period: 29.07.2025 to 15.02.2026",
        "Document Version: 1.1",
        "Prepared by: Jane Doe",
        "Reviewed by: John Roe",
    ],
    [
        "Executive Summary",
        "Two issues were identified in the payments API.",
        "",
        "Detailed Observations",
        "1. Broken Authentication",
        "Status: Closed",
        "Severity: High",
        "Detailed Observation:",
        "The API accepts requests with an empty encrypted payload.",
        "Impact:",
        "An attacker can submit unencrypted payment data.",
        "CVE/CWE:",
        "CWE-284: Improper Access Control",
        "Affected Asset:",
        "https://api.example.test/v2/pay",
        "Recommendation:",
        "Reject empty or invalid encrypted fields server-side.",
        "Reference: NA",
        "New or Repeat observation: Repeat",
    ],
    [
        "2. Business Logic Failure",
        "Status: Open",
        "Severity: Medium",
        "Detailed Observation:",
        "Negative transaction amounts are accepted.",
        "Recommendation:",
        "Validate amounts on the server.",
        "Proof of Concept:",
    ],
]


def make_image_bytes(size=(120, 120), color=(120, 180, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def make_pdf(path: Path, pages: List[List[str]], image_on_page: Optional[int] = None) -> Path:
    doc = fitz.open()
    for index, lines in enumerate(pages):
        page = doc.new_page()
        y = 60
        for line in lines:
            page.insert_text((50, y), line, fontsize=10)
            y += 16
        if image_on_page == index:
            page.insert_image(fitz.Rect(50, y + 10, 170, y + 130), stream=make_image_bytes())
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def report_pdf(tmp_path) -> Path:
    return make_pdf(tmp_path / "acme-report.pdf", REPORT_PAGES, image_on_page=2)


def make_docx(path: Path, members: dict) -> Path:
    """A minimal OOXML container with the given extra members."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types/>')
        z.writestr("word/document.xml",
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   "<w:body><w:p><w:r><w:t>Report text mentioning cmd.exe /c and /JavaScript</w:t></w:r></w:p>"
                   "</w:body></w:document>")
        for name, data in members.items():
            z.writestr(name, data)
    return path


class FakeBackend:
    """Scripted stand-in for a model server. ``responder(prompt, image, json_schema) -> str``."""

    description = "fake model"
    supports_json_schema = True

    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    def check(self):
        pass

    def generate(self, prompt, image=None, json_schema=None, max_tokens=8192):
        from report_to_json.backends import Generation

        self.calls.append({"prompt": prompt, "image": image, "json_schema": json_schema})
        result = self.responder(prompt, image, json_schema)
        if isinstance(result, Exception):
            raise result
        return result if isinstance(result, Generation) else Generation(text=result, truncated=False)

    def close(self):
        pass


def page_text_layer(pdf_path, page_no: int) -> str:
    with fitz.open(str(pdf_path)) as doc:
        return doc[page_no - 1].get_text()


def filled(keys, **values) -> dict:
    """A template-complete object for the given top-level sections."""
    from report_to_json import schema

    return {k: schema.conform(values.get(k), schema.template()[k]) for k in keys}


def finding(**values) -> dict:
    from report_to_json import schema

    return schema.conform(values, schema.template()["detailed_observations"][0])


def eicar() -> bytes:
    # Assembled at runtime so this source file is not itself flagged by anti-virus.
    return (r"X5O!P%@AP[4\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-" + "TEST-FILE!$H+H*").encode()
