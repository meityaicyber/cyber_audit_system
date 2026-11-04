"""
The decoupled two-pass model pipeline. One model (Qwen3-VL 4B Instruct AWQ) runs both passes.

Pass 1 (vision)  Each page is rendered with its images replaced by labelled
                 placeholder boxes and transcribed verbatim. The transcript is
                 checked against the PDF text layer; pages that dropped text are
                 re-transcribed, telling the model which words it missed.

Pass 2 (text)    The transcript is restructured into the master schema, one
                 section at a time so no single response exceeds the output limit:
                 front matter, scope/team/tools, executive summary, appendices, a
                 findings index, then one call per finding. On a server backend each
                 response is constrained to the section's JSON Schema; otherwise it is
                 validated and repaired. Prompts start with the transcript so a
                 prefix-caching server encodes it once.

Anything the model cannot do falls back to the text layer (pass 1) or the
rule-based parser (pass 2), and every fallback is recorded: a fallback means the
model pipeline failed for that part.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import fitz
import pdfplumber

from . import config, coverage, schema
from .schema import manual
from .backends import BackendError, ModelBackend
from .images import reconcile_tags, render_masked_page
from .storage import StoredImage
from .structurer import RuleBasedStructurer
from .transcribe import layout_page, page_block

log = logging.getLogger(__name__)

DetailFn = Callable[[str], None]
CancelFn = Callable[[], bool]


class Cancelled(Exception):
    pass


# --------------------------------------------------------------------------- pass 1

TRANSCRIBE_PROMPT = """TASK: transcribe page {page} of {pages}
You are transcribing one page of a cybersecurity audit report. Reproduce ALL text on the page exactly as written, in reading order, as GitHub-flavoured Markdown.

Rules:
1. Copy every word, number, URL, IP address, e-mail, CVE/CWE identifier, date and table cell verbatim. Do not summarise, paraphrase, correct, translate or skip anything - including headers, footers, page numbers, captions, footnotes and fine print.
2. Tables: Markdown tables with one row per table row and empty cells kept. Never merge, split or drop rows.
3. White boxes labelled with a tag of the form [IMAGE_PAGE_<page>_FIG_<n>] mark images that were removed. Write each label exactly as shown, on its own line, at the position of its box. Do not describe the box or guess what the image showed.
4. Use Markdown headings for headings and lists for lists.
5. Output only the transcription, with no commentary and no code fences.{retry}"""

RETRY_NOTE = """

Your previous transcription of this page was incomplete. These words appear on the page but were missing: {words}
Transcribe the entire page again, completely."""


@dataclass
class PageReport:
    page: int
    source: str                     # "model" | "text_layer_fallback"
    recall: Optional[float]         # None: no text layer to check against (scanned page)
    attempts: int
    issues: List[str] = field(default_factory=list)


def _strip_fences(text: str) -> str:
    return re.sub(r"^\s*```(?:markdown|md)?\s*\n|\n?```\s*$", "", text.strip(), flags=re.IGNORECASE)


class Pass1Transcriber:
    def __init__(self, backend: ModelBackend):
        self.backend = backend
        self.threshold = config.page_recall_threshold()
        self.retries = config.pass1_retries()
        self.dpi = config.render_dpi()

    def transcribe(self, pdf_path: str, images: Dict[int, List[StoredImage]],
                   detail: Optional[DetailFn] = None, cancel: Optional[CancelFn] = None
                   ) -> Tuple[str, List[PageReport]]:
        blocks: List[str] = []
        reports: List[PageReport] = []
        with fitz.open(pdf_path) as doc, pdfplumber.open(pdf_path) as plumb:
            for page in doc:
                if cancel and cancel():
                    raise Cancelled()
                no = page.number + 1
                if detail:
                    detail(f"page {no} of {len(doc)}")
                page_images = images.get(no, [])
                body, report = self._page(page, len(doc), page_images, plumb.pages[page.number])
                blocks.append(page_block(no, body))
                reports.append(report)
        return "\n\n".join(blocks), reports

    def _page(self, page: fitz.Page, pages: int, page_images: List[StoredImage], plumb_page):
        no = page.number + 1
        reference = coverage.reference_words(page, [i.bbox for i in page_images if i.bbox])
        image = render_masked_page(page, page_images, self.dpi)

        best: Optional[Tuple[str, Optional[float], List[str]]] = None  # (text, recall, words it missed)
        missing: List[str] = []  # from the latest attempt; drives the retry prompt
        issues: List[str] = []
        attempts = 0
        for attempt in range(1 + self.retries):
            attempts = attempt + 1
            retry = RETRY_NOTE.format(words=", ".join(missing[:40])) if missing else ""
            try:
                gen = self.backend.generate(TRANSCRIBE_PROMPT.format(page=no, pages=pages, retry=retry),
                                            image=image, max_tokens=8192)
            except BackendError as exc:
                issues.append(f"attempt {attempts}: {exc}")
                continue
            text = _strip_fences(gen.text)
            if gen.truncated:
                issues.append(f"attempt {attempts}: output hit the token limit")
            recall, missing = coverage.page_recall(reference, text)
            if best is None or (recall or 0) > (best[1] or 0):
                best = (text, recall, missing)
            if recall is None or recall >= self.threshold:
                break

        if best is None:  # every attempt failed: use the text layer, and say so
            issues.append("vision model failed on this page; text layer used")
            body, _ = reconcile_tags(layout_page(page, plumb_page, page_images), page_images)
            return body, PageReport(no, "text_layer_fallback", None, attempts, issues)

        text, recall, best_missing = best
        if recall is None:
            issues.append("no text layer: completeness could not be verified")
        elif recall < self.threshold:
            issues.append(f"recall {recall:.3f} below {self.threshold} after {attempts} attempt(s); "
                          f"missing words include {best_missing[:15]}")
        text, tag_issues = reconcile_tags(text, page_images)
        return text, PageReport(no, "model", recall, attempts, issues + tag_issues)


# --------------------------------------------------------------------------- pass 2

SECTIONS: List[Tuple[str, List[str], str]] = [
    ("front matter", ["report_meta", "document_control", "audit_timeline", "methodology"],
     "Report identification, document control (sign-offs, change history, distribution list), "
     "assessment dates and the standards/methodology referred to."),
    ("scope, team and tools", ["engagement_scope", "auditing_team", "tools_used"],
     "Every in-scope asset, exclusions, testing credentials/roles, every auditing team member and every tool."),
    ("executive summary", ["executive_summary"],
     "The report's own executive summary: totals, severity counts, the full narrative text and every row "
     "of its findings summary table."),
    ("appendices", ["appendices"],
     "The risk-rating criteria/matrix and any retest or closure records."),
]

INDEX_SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": {
        "type": "object",
        "properties": {"finding_id": {"type": ["string", "null"]}, "title": {"type": "string"},
                       "start_page": {"type": "integer"}, "end_page": {"type": "integer"}},
        "required": ["finding_id", "title", "start_page", "end_page"],
        "additionalProperties": False}}},
    "required": ["findings"],
    "additionalProperties": False,
}

# The transcript comes first so a prefix-caching server encodes it once per document;
# everything after it (task, structure, field guide, guardrails) varies per call.
STRUCTURE_PROMPT = """Below is the complete, verbatim transcript of a cybersecurity audit report. Pages are delimited by <!-- PAGE_START: n --> markers. Tags of the form [IMAGE_PAGE_<page>_FIG_<n>] are pointers to images held in storage.

<transcript>
{transcript}
</transcript>

TASK: {task}
{instruction}

Return one JSON object with exactly this structure (template notation: "string", "number", "boolean"; "YYYY-MM-DD" is an ISO date; "A | B" means one of the listed values):
{template}

FIELD GUIDE - where each field's content comes from:
{guide}

GUARDRAILS - these override everything else:
{guardrails}

Output only the JSON object.{repair}"""

FINDING_INSTRUCTION = """Extract finding {number} of {count}, titled "{title}" (identifier: {finding_id}), whose detailed description is on pages {start}-{end}. Only this finding: text from any neighbouring finding on the same pages is excluded."""

INDEX_INSTRUCTION = """List the report's findings with their identifiers, titles and page ranges."""


def parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    """The first JSON object in model output, tolerating code fences and stray prose."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    for candidate in (cleaned, cleaned[cleaned.find("{"): cleaned.rfind("}") + 1]):
        try:
            value = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict):
            return value
    return None


@dataclass
class SectionReport:
    name: str
    source: str  # "model" | "rule_based" | "empty"
    attempts: int
    issues: List[str] = field(default_factory=list)


_PAGE_BLOCK_RE = re.compile(r"<!-- PAGE_START: (\d+) -->.*?<!-- PAGE_END: \1 -->", re.DOTALL)


def _page_slice(transcript: str, start: int, end: int) -> str:
    """Pages ``start``..``end`` of the transcript (the whole transcript if none match)."""
    chosen = [m.group(0) for m in _PAGE_BLOCK_RE.finditer(transcript) if start <= int(m.group(1)) <= end]
    return "\n\n".join(chosen) or transcript


class Pass2Structurer:
    def __init__(self, backend: ModelBackend):
        self.backend = backend
        self.retries = config.pass2_retries()
        self._rule_based: Optional[Dict[str, Any]] = None

    def _fallback(self, transcript: str) -> Dict[str, Any]:
        if self._rule_based is None:
            self._rule_based = schema.conform(RuleBasedStructurer().structure(transcript))
        return self._rule_based

    def _call(self, transcript: str, task: str, instruction: str, template: Any, guide: str,
              json_schema: Dict[str, Any], max_tokens: int = 16384, accept_imperfect: bool = True
              ) -> Tuple[Optional[Dict], int, List[str]]:
        """Run one structuring call with validation and repair retries.

        If every attempt still breaks the schema but produced a JSON object with the
        expected keys, that output is kept (``accept_imperfect``): schema enforcement
        later nulls only the offending values and records them, which loses far less
        than replacing the whole section with the rule-based fallback.
        """
        issues: List[str] = []
        repair = ""
        usable: Optional[Dict] = None
        for attempt in range(1 + self.retries):
            prompt = STRUCTURE_PROMPT.format(transcript=transcript, task=task, instruction=instruction,
                                             template=json.dumps(template, indent=1), guide=guide,
                                             guardrails=manual.guardrails(), repair=repair)
            try:
                gen = self.backend.generate(prompt, json_schema=json_schema if self.backend.supports_json_schema
                                            else None, max_tokens=max_tokens)
            except BackendError as exc:
                issues.append(f"attempt {attempt + 1}: {exc}")
                continue
            if gen.truncated:
                issues.append(f"attempt {attempt + 1}: output hit the token limit")
                repair = "\n\nYour previous answer was cut off. Keep text complete but avoid repeating content."
                continue
            data = parse_json_object(gen.text)
            errors = ["output is not a JSON object"] if data is None else schema.validate_against(data, json_schema)
            if not errors:
                return data, attempt + 1, issues
            if data is not None and isinstance(template, dict) and any(k in data for k in template):
                usable = data
            issues.append(f"attempt {attempt + 1}: {'; '.join(errors[:5])}")
            repair = ("\n\nYour previous answer did not match the required structure: "
                      + "; ".join(errors[:10]) + "\nReturn the corrected, complete JSON object.")
        if accept_imperfect and usable is not None:
            issues.append("kept the last answer; values that break the schema are nulled at save")
            return usable, 1 + self.retries, issues
        return None, 1 + self.retries, issues

    def structure(self, transcript: str, detail: Optional[DetailFn] = None, cancel: Optional[CancelFn] = None
                  ) -> Tuple[Dict[str, Any], List[SectionReport]]:
        data: Dict[str, Any] = {}
        reports: List[SectionReport] = []

        def check_cancel():
            if cancel and cancel():
                raise Cancelled()

        for name, keys, instruction in SECTIONS:
            check_cancel()
            if detail:
                detail(name)
            result, attempts, issues = self._call(
                transcript, f"extract the {name}", instruction,
                {k: schema.template()[k] for k in keys}, manual.field_guide(keys), schema.section_schema(keys))
            if result is None:
                fallback = self._fallback(transcript)
                result = {k: fallback[k] for k in keys}
                reports.append(SectionReport(name, "rule_based", attempts, issues))
            else:
                reports.append(SectionReport(name, "model", attempts, issues))
            data.update({k: result.get(k) for k in keys})

        check_cancel()
        if detail:
            detail("findings index")
        index, attempts, issues = self._call(transcript, "index the findings", INDEX_INSTRUCTION,
                                             {"findings": [{"finding_id": "string", "title": "string",
                                                            "start_page": "number", "end_page": "number"}]},
                                             manual.blocks()[manual.FINDINGS_INDEX],
                                             INDEX_SCHEMA, max_tokens=8192, accept_imperfect=False)
        if index is None:
            reports.append(SectionReport("findings index", "rule_based", attempts, issues))
            data["detailed_observations"] = self._fallback(transcript)["detailed_observations"]
            return data, reports
        reports.append(SectionReport("findings index", "model", attempts, issues))

        entries = index["findings"]
        observations = []
        for n, entry in enumerate(entries, 1):
            check_cancel()
            if detail:
                detail(f"finding {n} of {len(entries)}")
            start, end = sorted((max(1, entry["start_page"]), max(1, entry["end_page"])))
            excerpt = _page_slice(transcript, start, end + 1)  # +1: evidence often spills onto the next page
            item_schema = schema.item_schema("detailed_observations")
            obs, attempts, issues = self._call(
                excerpt, f"extract finding {n}",
                FINDING_INSTRUCTION.format(number=n, count=len(entries), title=entry["title"],
                                           finding_id=entry["finding_id"], start=start, end=end),
                schema.template()["detailed_observations"][0], manual.field_guide(["detailed_observations"]),
                item_schema)
            name = f"finding {n}: {entry['title']}"
            if obs is None:
                obs = self._fallback_finding(transcript, entry)
                reports.append(SectionReport(name, "rule_based" if obs.get("_matched") else "empty", attempts, issues))
                obs.pop("_matched", None)
            else:
                reports.append(SectionReport(name, "model", attempts, issues))
            observations.append(obs)
        data["detailed_observations"] = observations
        return data, reports

    def _fallback_finding(self, transcript: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        wanted = re.sub(r"\W+", " ", entry["title"]).strip().lower()
        for obs in self._fallback(transcript)["detailed_observations"]:
            if re.sub(r"\W+", " ", obs.get("title") or "").strip().lower() == wanted:
                return {**obs, "_matched": True}
        stub = schema.conform({"finding_id": entry["finding_id"], "title": entry["title"]},
                              schema.template()["detailed_observations"][0])
        return stub
