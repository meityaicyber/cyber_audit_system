"""
Completeness checks for both passes.

Pass 1 (transcription):  ``page_recall`` compares the vision model's page transcript
    with the PDF's own text layer (words under masked images excluded). A page
    below the threshold is re-transcribed. Scanned pages have no text layer and
    cannot be checked; they are reported as unverifiable.

Pass 2 (structuring):    ``transcript_coverage`` splits the transcript into content
    units (text lines, table cells; structural text such as headings, contents
    pages, column headers and page furniture is set aside) and checks each against
    the text in the output JSON. ``unmapped_entries`` turns the uncovered units into
    paragraph-level ``unmapped_content`` entries, so nothing from the document is
    dropped silently.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Set, Tuple

import fitz

from .images import TAG_RE
from .textparse import join_wrapped_url, normalize_dates

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.\-/:@][a-z0-9]+)*")
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that the this to was were will with "
    "which not no any all can may be been being".split())
_PAGE_MARK_RE = re.compile(r"<!--\s*PAGE_(START|END):\s*(\d+)\s*-->")
_MD_NOISE_RE = re.compile(r"^\s*(?:#{1,6}\s*|[-*•▪]\s+|\d+[.)]\s+)?")


def tokens(text: str) -> List[str]:
    text = unicodedata.normalize("NFKC", text).lower()
    return _TOKEN_RE.findall(text)


def content_tokens(text: str) -> List[str]:
    return [t for t in tokens(text) if t not in _STOPWORDS and (len(t) > 2 or any(c.isdigit() for c in t))]


# --------------------------------------------------------------------------- pass 1

def reference_words(page: fitz.Page, masked_rects: Sequence[Sequence[float]]) -> List[str]:
    """Text-layer tokens of ``page``, excluding words inside masked image areas."""
    rects = [fitz.Rect(r) for r in masked_rects]
    words = []
    for x0, y0, x1, y1, word, *_ in page.get_text("words"):
        box = fitz.Rect(x0, y0, x1, y1)
        if any(box.intersects(r) and (box & r).get_area() > 0.5 * box.get_area() for r in rects):
            continue
        words.append(word)
    return tokens(" ".join(words))


def page_recall(reference: Sequence[str], transcript: str) -> Tuple[Optional[float], List[str]]:
    """(share of reference tokens reproduced, sample of missing tokens). None if nothing to check."""
    if not reference:
        return None, []
    want = Counter(reference)
    got = Counter(tokens(transcript))
    hit = sum(min(n, got[t]) for t, n in want.items())
    missing = [t for t, n in want.items() if got[t] < n]
    return hit / sum(want.values()), missing[:60]


# --------------------------------------------------------------------------- pass 2

_TOC_TITLES = {"contents", "table of contents", "index"}
_DOT_LEADER_RE = re.compile(r"^.{2,}?(?:\s*[.·…_]{3,}\s*|\s{2,})\d{1,3}$")
_PAGE_OF_RE = re.compile(r"^page\s+\d+(\s+of\s+\d+)?$", re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"\|?[\s\-:|]+\|?")


@dataclass
class Unit:
    """A piece of transcript content: a text line or a table cell."""
    index: int                    # position among content units (structural text excluded)
    page: Optional[int]
    heading: Optional[str]
    text: str
    source: str                   # "text" | "cell"
    row: Optional[str] = None     # the whole table row, for cells
    column: Optional[str] = None  # the column header, for cells


@dataclass
class Coverage:
    ratio: float                  # share of content tokens represented in the JSON
    uncovered: List[Unit]
    structural_units: int         # headings, TOC, column headers, page furniture (not content)


def _clean(piece: str) -> str:
    text = TAG_RE.sub(" ", _MD_NOISE_RE.sub("", piece)).strip(" *_`")
    return join_wrapped_url(text)


def _norm(text: str) -> str:
    return " ".join(tokens(text))


def _furniture(lines: List[str]) -> Set[str]:
    """Lines repeated on many pages: running headers and footers."""
    seen: dict = {}
    page = None
    pages = set()
    for raw in lines:
        line = raw.strip()
        mark = _PAGE_MARK_RE.fullmatch(line)
        if mark:
            page = int(mark.group(2))
            pages.add(page)
            continue
        if line and not line.startswith("|"):
            seen.setdefault(_norm(_clean(line)), set()).add(page)
    need = max(3, 0.25 * len(pages))
    return {text for text, on in seen.items() if text and len(on) >= need}


def transcript_units(markdown: str) -> Tuple[List[Unit], int]:
    """(content units, number of structural lines/cells skipped).

    Structural text is not content to be preserved: Markdown headings and label
    lines ("Assumptions:") become the ``heading`` of what follows; table-of-contents
    entries, table column headers, bare page numbers and running headers/footers are
    dropped. A line that repeats a table-of-contents entry is treated as a heading.
    """
    lines = markdown.splitlines()
    furniture = _furniture(lines)
    units: List[Unit] = []
    structural = 0
    page: Optional[int] = None
    heading: Optional[str] = None
    in_toc = False
    toc_entries: Set[str] = set()
    table_header: Optional[List[str]] = None

    def add(text, source, row=None, column=None):
        units.append(Unit(len(units), page, heading, text, source, row, column))

    for raw in lines:
        line = raw.strip()
        mark = _PAGE_MARK_RE.fullmatch(line)
        if mark:
            if mark.group(1) == "START":
                page = int(mark.group(2))
            else:
                in_toc = False
            table_header = None
            continue
        if not line or re.fullmatch(r"## Page \d+", line):
            table_header = None
            continue

        if line.startswith("|"):
            if _SEPARATOR_RE.fullmatch(line):
                continue
            cells = [_clean(c) for c in line.strip().strip("|").split("|")]
            if in_toc:
                structural += sum(1 for c in cells if content_tokens(c))
                continue
            if table_header is None:  # header row: column names are structure, values are content
                table_header = cells
                row_text = " | ".join(c for c in cells if c)
                for cell in cells:
                    if not content_tokens(cell):
                        continue
                    if any(ch.isdigit() for ch in cell) or len(cell.split()) > 8:
                        add(cell, "cell", row=row_text)
                    else:
                        structural += 1
                continue
            row_text = " | ".join(c for c in cells if c)
            for i, cell in enumerate(cells):
                if content_tokens(cell):
                    column = table_header[i] if i < len(table_header) and table_header[i] else None
                    add(cell, "cell", row=row_text, column=column)
            continue
        table_header = None

        text = _clean(line)
        if not content_tokens(text):
            continue
        key = _norm(text)
        if line.startswith("#") or key in toc_entries:
            heading = text
            in_toc = key in _TOC_TITLES
            structural += 1
            continue
        if key in _TOC_TITLES:
            heading, in_toc = text, True
            structural += 1
            continue
        if in_toc:
            if not re.fullmatch(r"\d{1,3}", text):  # "Introduction ....... 3" -> "introduction"
                toc_entries.add(_norm(re.sub(r"[\s.·…_]*\d{1,3}$", "", text)))
            structural += 1
            continue
        if (key in furniture or _PAGE_OF_RE.match(text) or re.fullmatch(r"\d{1,3}", text)
                or _DOT_LEADER_RE.match(text)):
            structural += 1
            continue
        if text.endswith(":") and len(text.split()) <= 6:
            heading = text.rstrip(": ")
            structural += 1
            continue
        add(text, "text")
    return units, structural


def _json_text(value: Any, out: List[str]) -> None:
    if isinstance(value, dict):
        for key, sub in value.items():
            if key in ("_meta", "unmapped_content"):
                continue
            out.append(key.replace("_", " "))  # field names cover label text such as "Release date"
            _json_text(sub, out)
    elif isinstance(value, list):
        for item in value:
            _json_text(item, out)
    elif value is not None:
        out.append(str(value))


def json_corpus(data: Any) -> Tuple[str, Set[str]]:
    parts: List[str] = []
    _json_text(data, parts)
    text = normalize_dates(" ".join(parts))
    return " ".join(tokens(text)), set(tokens(text))


def transcript_coverage(markdown: str, data: Any, min_token_share: float = 0.9) -> Coverage:
    """Which transcript content made it into ``data``'s schema fields."""
    corpus, vocab = json_corpus(data)
    units, structural = transcript_units(markdown)
    total = covered = 0
    uncovered: List[Unit] = []
    for unit in units:
        unit_tokens = content_tokens(normalize_dates(unit.text))
        weight = len(unit_tokens)
        total += weight
        share = sum(1 for t in unit_tokens if t in vocab) / weight
        if " ".join(tokens(normalize_dates(unit.text))) in corpus or share >= min_token_share:
            covered += weight
        else:
            uncovered.append(unit)
    return Coverage(covered / total if total else 1.0, uncovered, structural)


def unmapped_entries(units: Iterable[Unit]) -> List[dict]:
    """Group uncovered units into ``unmapped_content`` entries.

    Consecutive uncovered lines under the same heading are one paragraph (even across
    a page break); table cells keep their column and row as context. Exact
    duplicates (e.g. a table and its text rendering) are kept once.
    """
    entries: List[dict] = []
    seen: Set[str] = set()
    last: Optional[Unit] = None
    for unit in units:
        joinable = (last is not None and unit.source == "text" and last.source == "text"
                    and unit.index == last.index + 1 and unit.heading == last.heading)
        if joinable:
            if unit.text != last.text:  # a line repeated back-to-back is one line
                entries[-1]["text"] += " " + unit.text
        else:
            context = None
            if unit.source == "cell":
                parts = ([f"column: {unit.column}"] if unit.column else []) + [f"row: {unit.row}"]
                context = "; ".join(parts)
            entries.append({"page": unit.page, "heading": unit.heading,
                            "kind": "table_data" if unit.source == "cell" else "text",
                            "text": unit.text, "context": context})
        last = unit

    out = []
    for entry in entries:
        if entry["kind"] == "text":
            entry["kind"] = "narrative" if len(entry["text"].split()) >= 6 else "other"
        key = _norm(entry["text"]) + "|" + entry["kind"]
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


