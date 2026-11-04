"""
Text-layer transcription (fallback only).

Used when the vision model cannot transcribe a page (or at all). Builds the same
page-marked Markdown as pass 1 from the PDF's own text layer: pdfplumber tables
plus PyMuPDF text blocks in reading order, with image tags placed where the
images are drawn. Scanned pages have no text layer and come out empty.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

import fitz  # PyMuPDF
import pdfplumber

from .storage import StoredImage


def format_markdown_table(raw_table: List[List[Any]]) -> str:
    """Render a 2-D list of cells as a Markdown table (first row is the header)."""
    rows: List[List[str]] = []
    for row in raw_table or []:
        if not row:
            continue
        cells = [
            "" if cell is None else str(cell).replace("\r\n", " ").replace("\n", " ").replace("|", "&#124;").strip()
            for cell in row
        ]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header = rows[0] if any(rows[0]) else [f"Col {i + 1}" for i in range(width)]

    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def page_block(page_no: int, body: str) -> str:
    return f"<!-- PAGE_START: {page_no} -->\n## Page {page_no}\n\n{body.strip()}\n\n<!-- PAGE_END: {page_no} -->"


def layout_page(page: fitz.Page, plumb_page, images: Sequence[StoredImage]) -> str:
    """Markdown for one page from its text layer.

    The page's tables come first, then its full text flow. Table text therefore
    appears twice; the rule-based parser relies on both renderings (some reports
    only parse cleanly from one or the other), and reordering them was measured to
    misattribute text between fields, so this layout is deliberate.
    """
    parts: List[str] = []
    for table in plumb_page.extract_tables():
        md = format_markdown_table(table)
        if md:
            parts.append(md)

    blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
    placed = sorted((i for i in images if i.bbox), key=lambda i: (i.bbox[1], i.bbox[0]))
    unplaced = [i for i in images if not i.bbox]
    flow: List[str] = []
    for block in blocks:
        while placed and placed[0].bbox[1] <= block[1]:
            flow.append(placed.pop(0).tag)
        flow.append(block[4].strip())
    flow += [i.tag for i in placed + unplaced]
    parts.append("\n".join(flow))
    return "\n\n".join(p for p in parts if p)


def transcribe_pdf(pdf_path: str, images_by_page: Dict[int, List[StoredImage]]) -> str:
    """Whole-document text-layer transcript, page-marked like pass 1."""
    blocks = []
    with fitz.open(pdf_path) as doc, pdfplumber.open(pdf_path) as plumb:
        for page in doc:
            no = page.number + 1
            blocks.append(page_block(no, layout_page(page, plumb.pages[page.number], images_by_page.get(no, []))))
    return "\n\n".join(blocks)
