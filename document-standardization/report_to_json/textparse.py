"""Low-level helpers for parsing intermediate Markdown transcripts."""

from __future__ import annotations

import datetime as _dt
import ipaddress
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

PLACEHOLDER_VALUES = {"", "-", "--", "—", "–", "n/a.", "nil"}

# No TLD required: redacted reports often show addresses like "name@com".
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IMAGE_TOKEN_RE = re.compile(r"\[IMAGE_(?:PAGE_(\d+)_FIG_\d+|DOCX_FIG_\d+)\]")
PAGE_START_RE = re.compile(r"<!-- PAGE_START: (\d+) -->")
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
CVSS_VECTOR_RE = re.compile(r"\b(?:CVSS:\d\.\d/)?AV:[NALP]/AC:[LH]/(?:AT:[NP]/)?PR:[NLH]/UI:[NRPA]/\S+")

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# --------------------------------------------------------------------------- values

def clean_value(value: Optional[str]) -> Optional[str]:
    """Collapse whitespace; map empty/dash placeholders to None. Keeps literal 'NA'."""
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value.replace("&#124;", "|")).strip(" :•")
    return None if value.lower() in PLACEHOLDER_VALUES else value


def serial(cell: str) -> Optional[int]:
    """Row serial number from cells like '3' or '3.'."""
    m = re.fullmatch(r"\s*(\d{1,4})\.?\s*", cell or "")
    return int(m.group(1)) if m else None


def norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("&#124;", "|")).strip(" :.-•").lower()


def join_wrapped_url(cell: str) -> str:
    """Undo PDF line-wrapping inside a cell that holds a single URL."""
    cell = cell.strip()
    if cell.lower().startswith(("http://", "https://")) and cell.lower().count("http") == 1:
        return re.sub(r"\s+", "", cell)
    return cell


def is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


# --------------------------------------------------------------------------- dates

def parse_date(text: Optional[str]) -> Optional[str]:
    """Parse the first recognisable date in ``text`` into ISO ``YYYY-MM-DD``.

    Numeric dates are read day-first (DD.MM.YYYY), matching CERT-In style reports,
    unless the first number cannot be a day-first month.
    """
    if not text:
        return None
    s = re.sub(r"(\d{1,2})\s*(?:st|nd|rd|th)\b", r"\1", text, flags=re.IGNORECASE)

    candidates: List[Tuple[int, int, int, int]] = []  # (position, y, m, d)
    for m in re.finditer(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", s):
        candidates.append((m.start(), int(m[1]), int(m[2]), int(m[3])))
    for m in re.finditer(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b", s):
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        if mo > 12 and d <= 12:
            d, mo = mo, d
        candidates.append((m.start(), y + 2000 if y < 100 else y, mo, d))
    for m in re.finditer(r"\b(\d{1,2})[\s\-./,]*([A-Za-z]{3,9})\.?[\s\-./,]*(\d{4}|\d{2})\b", s):
        mo = _MONTHS.get(m[2][:3].lower())
        if mo:
            year = int(m[3])
            candidates.append((m.start(), year + 2000 if year < 100 else year, mo, int(m[1])))
    for m in re.finditer(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b", s):
        mo = _MONTHS.get(m[1][:3].lower())
        if mo:
            candidates.append((m.start(), int(m[3]), mo, int(m[2])))

    for _, y, mo, d in sorted(candidates):
        try:
            return _dt.date(y, mo, d).isoformat()
        except ValueError:
            continue
    return None


DATE_RE = re.compile(
    r"\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b"
    r"|\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?[\s\-./,]*[A-Za-z]{3,9}\.?[\s\-./,]*(?:\d{4}|\d{2})\b"
    r"|\b[A-Za-z]{3,9}\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",
    re.IGNORECASE,
)


def find_dates(text: str) -> List[str]:
    """All parseable dates in order of appearance (ISO strings)."""
    return [iso for iso in (parse_date(m.group(0)) for m in DATE_RE.finditer(text)) if iso]


def normalize_dates(text: str) -> str:
    """Rewrite every parseable date in ``text`` as ISO ``YYYY-MM-DD``."""
    return DATE_RE.sub(lambda m: parse_date(m.group(0)) or m.group(0), text)


def date_field(raw: Optional[str]) -> Optional[str]:
    """ISO date when parseable, else the cleaned original text (flagged by validation)."""
    raw = clean_value(raw)
    if raw is None:
        return None
    return parse_date(raw) or raw


# --------------------------------------------------------------------------- tables

@dataclass
class MdTable:
    rows: List[List[str]]  # header row first, separator removed
    start: int              # character offset in the transcript
    page: Optional[int]


def parse_tables(markdown: str) -> List[MdTable]:
    tables: List[MdTable] = []
    pages = page_index(markdown)
    block: List[str] = []
    block_start = 0
    offset = 0
    for line in markdown.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1:
            if not block:
                block_start = offset
            if not re.fullmatch(r"\|[\s\-:|]+\|", stripped):
                block.append(stripped)
        elif block:
            tables.append(_make_table(block, block_start, pages))
            block = []
        offset += len(line)
    if block:
        tables.append(_make_table(block, block_start, pages))
    return [t for t in tables if t.rows]


def _make_table(lines: List[str], start: int, pages) -> MdTable:
    rows = [[c.strip().replace("&#124;", "|") for c in ln[1:-1].split("|")] for ln in lines]
    return MdTable(rows=rows, start=start, page=page_at(pages, start))


def compact(cells: List[str]) -> List[str]:
    """Drop empty cells and consecutive duplicates produced by merged PDF cells."""
    out: List[str] = []
    for c in cells:
        c = c.strip()
        if c and (not out or out[-1] != c):
            out.append(c)
    return out


# --------------------------------------------------------------------------- pages

def page_index(markdown: str) -> List[Tuple[int, int]]:
    return [(m.start(), int(m.group(1))) for m in PAGE_START_RE.finditer(markdown)]


def page_at(pages: List[Tuple[int, int]], pos: int) -> Optional[int]:
    current = None
    for start, number in pages:
        if start > pos:
            break
        current = number
    return current


# --------------------------------------------------------------------------- prose

_NOISE_LINE_RE = re.compile(
    r"^\s*(?:<!-- PAGE_(?:START|END): \d+ -->|## Page \d+|### (?:Page Text Content|Embedded Visual Elements|"
    r"Table [\d.]+|Other Embedded Images)|---|Page \d+ of \d+|[ivx]{1,4}\.?)\s*$",
    re.IGNORECASE,
)
_RUNNING_HEADER_RE = re.compile(r"^(?:CONFIDENTIAL|RESTRICTED|INTERNAL(?: USE ONLY)?)$")


def prose_lines(text: str) -> List[str]:
    """Text lines with page markers, table rows and image lines removed."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or _NOISE_LINE_RE.match(s) or (s.startswith("|") and s.endswith("|")):
            continue
        if IMAGE_TOKEN_RE.match(s):
            continue
        out.append(s)
    return out


def prose(text: str) -> Optional[str]:
    """Join wrapped lines into readable text, keeping bullets on their own lines."""
    lines = [ln for ln in prose_lines(text) if not _RUNNING_HEADER_RE.match(ln)]
    merged: List[str] = []
    pending_bullet = False
    for s in lines:
        if s in ("•", "*", "▪"):
            pending_bullet = True
            continue
        if pending_bullet or s.startswith("•"):
            merged.append("\n• " + s.lstrip("• ").strip())
        else:
            merged.append((" " if merged else "") + s)
        pending_bullet = False
    result = re.sub(r"[ \t]+", " ", "".join(merged)).strip()
    return clean_value(result) if "\n" not in result else result
