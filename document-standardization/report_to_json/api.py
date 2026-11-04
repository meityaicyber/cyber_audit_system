"""
Integration entry points.

    from report_to_json import standardize_report

    response = standardize_report("path/to/report.pdf")   # JSON text: the standardised report

``standardize_report`` takes a report and returns the JSON that the pipeline
produced for it. That JSON is the output: exactly the structure of
``master_schema.json``, identical to the ``<name>.json`` file written alongside.

It returns whenever a result exists, including when the fallback had to be used
(this is logged as a warning and recorded in the run report). Pass ``strict=True``
to get ``ModelPipelineFailed`` instead, or use ``process_report`` when the caller
needs the run status and report next to the JSON.

The pipeline (and with it the model) is created once per process and reused.
Calls are serialised: one document is processed at a time.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional, Union

from . import config
from .pipeline import DocumentPipeline, PipelineError, PipelineResult

log = logging.getLogger(__name__)

PathLike = Union[str, "os.PathLike[str]"]

_lock = threading.Lock()
_pipeline: Optional[DocumentPipeline] = None


class ModelPipelineFailed(PipelineError):
    """The model could not produce the result and the fallback was used instead.

    ``result`` holds what the fallback produced (``result.data``) and why
    (``result.meta["status_reasons"]``); the output files were written.
    """

    def __init__(self, result: PipelineResult):
        self.result = result
        reasons = "; ".join(result.meta.get("status_reasons") or result.warnings) or "no reason recorded"
        super().__init__(f"Model pipeline failed, fallback output only: {reasons}")


def process_report(report_path: PathLike, output_dir: Optional[PathLike] = None, save_to_disk: bool = True) -> PipelineResult:
    """Run the full pipeline on one report and return the complete result.

    ``result.data`` is the master-schema JSON as a dict, ``result.status`` is "ok",
    "needs_review" or "fallback", ``result.meta`` is the run report, and
    ``result.json_path`` / ``result.meta_path`` are the files written.

    Raises ``PipelineError`` if the file is missing, of an unsupported type, or could not be processed.
    """
    global _pipeline
    if save_to_disk:
        out_dir = Path(output_dir) if output_dir is not None else config.DEFAULT_OUTPUT_DIR
    else:
        out_dir = None
        
    with _lock:
        if _pipeline is None:
            _pipeline = DocumentPipeline()
            
    return _pipeline.process_file(Path(report_path), out_dir)


def standardize_report(report_path: PathLike, output_dir: Optional[PathLike] = None, *,
                       strict: bool = False) -> str:
    """Convert one audit report (PDF) and return the standardised JSON.

    Parameters
    ----------
    report_path : path to the report.
    output_dir : where ``<name>.json``, ``<name>.meta.json`` and the transcript are
        also written. Defaults to the project's ``outputs/`` folder.
    strict : raise ``ModelPipelineFailed`` instead of returning JSON that the
        fallback produced.

    Returns
    -------
    The JSON document as text, with exactly the structure of ``master_schema.json``.
    Fields the report does not state are ``null``.

    Raises
    ------
    PipelineError : the file is missing, of an unsupported type, or could not be
        processed. In these cases no JSON exists to return.
    """
    result = process_report(report_path, output_dir)
    if result.status == "fallback":
        if strict:
            raise ModelPipelineFailed(result)
        log.warning("%s: model pipeline failed, returning fallback output (%s)", Path(report_path).name,
                    "; ".join(result.meta.get("status_reasons") or result.warnings))
    return json.dumps(result.data, indent=2, ensure_ascii=False)


def close() -> None:
    """Release the model held by this process (the next call sets it up again)."""
    global _pipeline
    with _lock:
        if _pipeline is not None:
            _pipeline.close()
            _pipeline = None
