"""
The document standardisation pipeline. Every front-end calls ``DocumentPipeline.process_file``.

  0  Malware pre-gate on the file as received (fails closed)
  1  Normalise to PDF (DOCX converted after passing the gate, then re-scanned)
  2  Offload images to deep storage; each placement gets a pointer tag
  3  Pass 1: the model (Qwen3-VL 4B Instruct AWQ) transcribes every page (images masked by their tags)
  4  Pass 2: the same model restructures the transcript into the master schema
  5  Enforce the master schema, check completeness, save

Outputs:
  <name>.json        exactly the structure of master_schema.json, nothing else
  <name>.meta.json   the sidecar: run status and reports, coverage,
                     ``unmapped_content`` (transcript text no schema field holds) and
                     ``dropped_values`` (values the schema's types/lists cannot hold)

Run status (``status`` in the sidecar):
  ok            both passes ran on the model and every completeness check passed
  needs_review  model output, but a check failed (low page recall, low coverage,
                missing image tags, schema issues)
  fallback      the model pipeline failed somewhere and the text layer or the
                rule-based parser was used instead
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import __version__, config, coverage, schema
from .backends import BackendError, ModelBackend, create_backend
from .images import offload_images
from .storage import DeepStorage, LocalDeepStorage, build_manifest
from .structurer import RuleBasedStructurer
from .transcribe import transcribe_pdf
from .vlm import Cancelled, Pass1Transcriber, Pass2Structurer

log = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = (".pdf",)

STAGES = [
    "Offloading images to deep storage",
    "Pass 1: vision transcription",
    "Pass 2: schema structuring",
    "Completeness check and save",
]

ProgressFn = Callable[[int, str], None]
CancelFn = Callable[[], bool]


class PipelineError(Exception):
    """The document could not be processed."""


class PipelineCancelled(Exception):
    """Processing was cancelled by the caller."""


def safe_stem(stem: str) -> str:
    """Filesystem-safe output name (Windows drops trailing spaces/dots from directory names)."""
    return re.sub(r"[^\w.\-]+", "_", stem).strip("._ ") or "document"


@dataclass
class PipelineResult:
    data: Dict[str, Any]   # exactly the master schema
    meta: Dict[str, Any]   # run report, unmapped_content, dropped_values (the sidecar)
    status: str
    json_path: Optional[Path]
    meta_path: Optional[Path]
    transcript_path: Optional[Path]
    manifest_path: str
    elapsed_seconds: float
    warnings: List[str] = field(default_factory=list)


class DocumentPipeline:
    def __init__(self, model: str = config.DEFAULT_MODEL,
                 storage: Optional[DeepStorage] = None, backend: Optional[ModelBackend] = None):
        self.profile = config.get_model(model)
        self.storage = storage or LocalDeepStorage(config.deep_storage_dir())
        self._backend = backend

    def _get_backend(self) -> ModelBackend:
        if self._backend is None:
            self._backend = create_backend(self.profile.key)
        return self._backend

    def close(self) -> None:
        if self._backend is not None:
            self._backend.close()
            self._backend = None

    # ------------------------------------------------------------------ main entry

    def process_file(self, input_path, output_dir=None, progress: Optional[ProgressFn] = None,
                     cancel: Optional[CancelFn] = None) -> PipelineResult:
        started = _dt.datetime.now()
        src = Path(input_path)
        warnings: List[str] = []

        def step(index: int, detail: str = "") -> None:
            if cancel and cancel():
                raise PipelineCancelled()
            log.info("[%d/%d] %s %s", index + 1, len(STAGES), STAGES[index], detail)
            if progress:
                progress(index, f"{STAGES[index]} - {detail}" if detail else STAGES[index])

        if not src.is_file():
            raise PipelineError(f"Input file not found: {src}")
        if src.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise PipelineError(f"Unsupported file type {src.suffix!r}; expected one of {SUPPORTED_SUFFIXES}")

        stem = safe_stem(src.stem)
        json_path = None
        meta_path = None
        transcript_path = None
        if output_dir is not None:
            out_dir = Path(output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            json_path = out_dir / f"{stem}.json"
            meta_path = out_dir / f"{stem}.meta.json"
            transcript_path = out_dir / f"{stem}_transcript.md"

        pdf = src

        # 0. Images to deep storage, replaced by pointer tags.
        step(0)
        document_id = f"{stem}-({_sha256(src)})[:12]"
        offload = offload_images(str(pdf), self.storage)
        images = offload.figures
        manifest_path = self.storage.write_manifest(
            document_id, build_manifest(document_id, src.name, offload.all_figures(), offload.layout))

        # 1-2. The two model passes (or the recorded fallback).
        model_meta: Dict[str, Any] = {"key": self.profile.key, "repo_id": self.profile.repo_id}
        try:
            backend = self._get_backend()
            backend.check()
            model_meta["backend"] = backend.description
        except BackendError as exc:
            backend = None
            model_meta["unavailable"] = str(exc)
            warnings.append(f"MODEL PIPELINE FAILED - {exc}. Output comes from the rule-based fallback.")

        try:
            if backend is not None:
                step(1)
                transcript, page_reports = Pass1Transcriber(backend).transcribe(
                    str(pdf), images, detail=lambda d: step(1, d), cancel=cancel)
            else:
                step(1, "fallback: text layer")
                transcript, page_reports = transcribe_pdf(str(pdf), images), []
            if transcript_path:
                transcript_path.write_text(transcript, encoding="utf-8")

            if backend is not None:
                step(2)
                data, section_reports = Pass2Structurer(backend).structure(
                    transcript, detail=lambda d: step(2, d), cancel=cancel)
            else:
                step(2, "fallback: rule-based parser")
                data, section_reports = RuleBasedStructurer().structure(transcript), []
        except Cancelled as exc:
            raise PipelineCancelled() from exc

        # 3. Exactly the master schema in the output; everything else in the sidecar.
        step(3)
        data, dropped = schema.enforce(data)
        errors = schema.validate(data)  # always empty after enforce; kept as a guard
        cov = coverage.transcript_coverage(transcript, data)
        unmapped = coverage.unmapped_entries(cov.uncovered)
        status, reasons = _status(backend is not None, page_reports, section_reports, cov.ratio, errors, dropped)
        warnings += reasons

        elapsed = (_dt.datetime.now() - started).total_seconds()
        meta = {
            "status": status,
            "status_reasons": reasons,
            "pipeline_version": __version__,
            "source_file": src.name,
            "source_sha256": _sha256(src),
            "document_id": document_id,
            "image_manifest": manifest_path,
            "processed_at": started.isoformat(timespec="seconds"),
            "elapsed_seconds": round(elapsed, 2),
            "model": model_meta,
            "pass1_pages": [asdict(r) for r in page_reports],
            "pass2_sections": [asdict(r) for r in section_reports],
            "coverage": {"placed_in_schema": round(cov.ratio, 4),
                         "unmapped_entries": len(unmapped),
                         "structural_units_skipped": cov.structural_units,
                         "threshold": config.coverage_threshold()},
            "validation_errors": errors,
            "missing_fields": schema.missing_fields(data),
            "dropped_values": dropped,
            "unmapped_content": unmapped,
        }
        if json_path:
            json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if meta_path:
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Processed %s: status=%s, %d findings, coverage %.1f%%, %.1fs", src.name, status,
                 len(data["detailed_observations"]), cov.ratio * 100, elapsed)
        return PipelineResult(data, meta, status, json_path, meta_path, transcript_path, manifest_path,
                              elapsed, warnings)

    # ------------------------------------------------------------------ helpers

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _status(model_ran: bool, pages, sections, coverage_ratio: float, errors: List[str],
            dropped: Optional[List[Dict[str, Any]]] = None):
    reasons: List[str] = []
    if not model_ran:
        return "fallback", ["model unavailable: whole document produced by the rule-based fallback"]
    fallback_pages = [p.page for p in pages if p.source != "model"]
    fallback_sections = [s.name for s in sections if s.source != "model"]
    if fallback_pages:
        reasons.append(f"pass 1 fell back to the text layer on page(s) {fallback_pages}")
    if fallback_sections:
        reasons.append(f"pass 2 fell back for: {fallback_sections}")
    if reasons:
        return "fallback", reasons

    threshold = config.page_recall_threshold()
    low = [p.page for p in pages if p.recall is not None and p.recall < threshold]
    tag_issues = [p.page for p in pages if any("tag" in i for i in p.issues)]
    if low:
        reasons.append(f"page recall below {threshold} on page(s) {low}")
    if tag_issues:
        reasons.append(f"image tags repaired on page(s) {tag_issues}")
    if coverage_ratio < config.coverage_threshold():
        reasons.append(f"only {coverage_ratio:.1%} of transcript text placed in schema fields "
                       f"(rest kept in unmapped_content)")
    if errors:
        reasons.append(f"{len(errors)} schema validation issue(s)")
    if dropped:
        reasons.append(f"{len(dropped)} value(s) the master schema cannot hold were set to null "
                       f"(originals in dropped_values)")
    return ("needs_review" if reasons else "ok"), reasons
