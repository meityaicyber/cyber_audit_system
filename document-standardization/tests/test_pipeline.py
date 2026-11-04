import json
import re

import pytest

from report_to_json import pipeline as pipeline_mod
from report_to_json import schema
from report_to_json.backends import BackendError, Generation
from report_to_json.pipeline import (DocumentBlocked, DocumentPipeline, PipelineCancelled, PipelineError,
                                     safe_stem)
from report_to_json.security import gate as gate_mod
from report_to_json.storage import LocalDeepStorage

from conftest import REPORT_PAGES, FakeBackend, filled, finding, make_pdf, page_text_layer

TAGS = {3: "[IMAGE_PAGE_3_FIG_1]"}

SECTION_REPLIES = {
    "extract the front matter": filled(
        ["report_meta", "document_control", "audit_timeline", "methodology"],
        report_meta={"report_title": "Acme Payments API Assessment Report", "report_release_date": "2026-02-16",
                     "report_type": "API Assessment", "audit_type": "Follow Up Report", "report_version": "1.1",
                     "audit_period": {"from": "2025-07-29", "to": "2026-02-15"}},
        document_control={"document_version": "1.1", "prepared_by": {"name": "Jane Doe"},
                          "reviewed_by": {"name": "John Roe"}}),
    "extract the scope, team and tools": filled(["engagement_scope", "auditing_team", "tools_used"]),
    "extract the executive summary": filled(
        ["executive_summary"], executive_summary={"narrative": "Two issues were identified in the payments API.",
                                                  "total_findings": 2}),
    "extract the appendices": filled(["appendices"]),
    "index the findings": {"findings": [
        {"finding_id": "1", "title": "Broken Authentication", "start_page": 2, "end_page": 2},
        {"finding_id": "2", "title": "Business Logic Failure", "start_page": 3, "end_page": 3}]},
    "extract finding 1": finding(
        finding_id="1", title="Broken Authentication", status="Closed", severity="High",
        observation_description="The API accepts requests with an empty encrypted payload.",
        impact="An attacker can submit unencrypted payment data.", cwe=["CWE-284: Improper Access Control"],
        affected_asset=["https://api.example.test/v2/pay"], reference="NA", new_or_repeat="Repeat",
        recommendation="Reject empty or invalid encrypted fields server-side."),
    "extract finding 2": finding(
        finding_id="2", title="Business Logic Failure", status="Open", severity="Medium",
        observation_description="Negative transaction amounts are accepted.",
        recommendation="Validate amounts on the server.",
        proof_of_concept=[{"sr_no": 1, "type": "image", "reference": "[IMAGE_PAGE_3_FIG_1]", "is_retest": False}]),
}


def perfect_model(pdf_path, overrides=None):
    """Transcribes pages from the text layer (plus tags) and answers pass-2 tasks from SECTION_REPLIES."""
    overrides = overrides or {}

    def respond(prompt, image, json_schema):
        task = re.search(r"TASK: (.+)", prompt).group(1).strip()
        if task in overrides:
            return overrides[task](prompt) if callable(overrides[task]) else overrides[task]
        page = re.match(r"transcribe page (\d+) of", task)
        if page:
            n = int(page.group(1))
            return page_text_layer(pdf_path, n) + ("\n" + TAGS[n] if n in TAGS else "")
        return json.dumps(SECTION_REPLIES[task])
    return FakeBackend(respond)


def run(pdf, tmp_path, backend, **kwargs):
    pipe = DocumentPipeline(backend=backend, storage=LocalDeepStorage(tmp_path / "store"), **kwargs)
    return pipe.process_file(pdf, tmp_path / "out")


@pytest.fixture(autouse=True)
def _lenient_coverage(monkeypatch):
    monkeypatch.setenv("COVERAGE_THRESHOLD", "0.8")


def test_full_model_route(report_pdf, tmp_path):
    backend = perfect_model(report_pdf)
    stages = []
    pipe = DocumentPipeline(backend=backend, storage=LocalDeepStorage(tmp_path / "store"))
    result = pipe.process_file(report_pdf, tmp_path / "out", progress=lambda i, d: stages.append(i))

    assert result.status == "ok", result.meta["status_reasons"]
    assert sorted(set(stages)) == [0, 1, 2, 3, 4, 5]
    data = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert [o["title"] for o in data["detailed_observations"]] == ["Broken Authentication", "Business Logic Failure"]
    assert data["detailed_observations"][1]["proof_of_concept"][0]["reference"] == "[IMAGE_PAGE_3_FIG_1]"

    meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
    assert meta == result.meta
    assert [p["source"] for p in meta["pass1_pages"]] == ["model"] * 3
    assert all(p["recall"] == 1.0 for p in meta["pass1_pages"])
    assert all(s["source"] == "model" for s in meta["pass2_sections"])
    assert meta["model"]["backend"] == "fake model"
    manifest = json.loads(open(meta["image_manifest"], encoding="utf-8").read())
    assert list(manifest["images"]) == ["[IMAGE_PAGE_3_FIG_1]"]

    # Pass 1 saw rendered pages; pass 2 calls were constrained by a schema and started with the transcript.
    page_calls = [c for c in backend.calls if c["image"] is not None]
    assert len(page_calls) == 3
    structure_calls = [c for c in backend.calls if c["image"] is None]
    assert all(c["json_schema"] for c in structure_calls)
    assert all(c["prompt"].startswith("Below is the complete, verbatim transcript") for c in structure_calls)
    # Per-finding calls only get that finding's pages (plus one).
    finding2 = next(c for c in structure_calls if "TASK: extract finding 2" in c["prompt"])
    assert "<!-- PAGE_START: 3 -->" in finding2["prompt"] and "<!-- PAGE_START: 1 -->" not in finding2["prompt"]


def _same_shape(value, node, path="$"):
    """Assert ``value`` has exactly the template's keys at every level."""
    if isinstance(node, dict):
        assert isinstance(value, dict) and set(value) == set(node), f"{path}: keys {sorted(value)}"
        for key, sub in node.items():
            _same_shape(value[key], sub, f"{path}.{key}")
    elif isinstance(node, list):
        assert isinstance(value, list), path
        for i, item in enumerate(value):
            _same_shape(item, node[0], f"{path}[{i}]")


def test_output_file_is_exactly_the_master_schema(report_pdf, tmp_path):
    result = run(report_pdf, tmp_path, perfect_model(report_pdf))
    saved = json.loads(result.json_path.read_text(encoding="utf-8"))
    _same_shape(saved, schema.template())
    assert schema.validate(saved) == []
    assert "_meta" not in saved and "unmapped_content" not in saved
    assert result.meta_path.name == "acme-report.meta.json"


def test_values_the_schema_cannot_hold_are_nulled_and_recorded(report_pdf, tmp_path):
    odd = finding(finding_id="1", title="Broken Authentication", status="closed", cvss_score="7.5",
                  observation_date="16.02.2026")
    odd["severity"] = "Informational"          # not in the schema's severity list
    odd["cvss_score"] = "7.5"                  # number given as text: normalised
    odd["impact_level"] = 3                    # wrong type
    odd["exploitability"] = "Easy"             # key the schema does not define
    backend = perfect_model(report_pdf, {"extract finding 1": json.dumps(odd)})
    backend.supports_json_schema = False       # as with the in-process backend (no constrained decoding)
    result = run(report_pdf, tmp_path, backend)

    obs = json.loads(result.json_path.read_text(encoding="utf-8"))["detailed_observations"][0]
    assert obs["severity"] is None and obs["impact_level"] is None and "exploitability" not in obs
    assert (obs["status"], obs["cvss_score"], obs["observation_date"]) == ("Closed", 7.5, "2026-02-16")
    dropped = {d["path"]: d["value"] for d in result.meta["dropped_values"]}
    assert dropped == {"detailed_observations[0].severity": "Informational",
                       "detailed_observations[0].impact_level": 3,
                       "detailed_observations[0].exploitability": "Easy"}
    assert result.status == "needs_review"


def test_text_not_placed_in_fields_is_kept_in_unmapped_content(tmp_path):
    pages = [REPORT_PAGES[0] + ["This report is intended solely for internal use by Acme."]] + REPORT_PAGES[1:]
    pdf = make_pdf(tmp_path / "r.pdf", pages, image_on_page=2)
    result = run(pdf, tmp_path, perfect_model(pdf))
    assert {"page": 1, "heading": None, "kind": "narrative", "context": None,
            "text": "This report is intended solely for internal use by Acme."} in result.meta["unmapped_content"]
    assert result.meta["coverage"]["unmapped_entries"] >= 1


def test_low_coverage_needs_review(report_pdf, tmp_path, monkeypatch):
    monkeypatch.setenv("COVERAGE_THRESHOLD", "0.999")
    empty = {t: json.dumps(v) for t, v in SECTION_REPLIES.items()}
    empty["extract the executive summary"] = json.dumps(filled(["executive_summary"]))
    result = run(report_pdf, tmp_path, perfect_model(report_pdf, empty))
    assert result.status == "needs_review"
    assert any("placed in schema" in r for r in result.meta["status_reasons"])


def test_incomplete_page_is_retried_with_missing_words(report_pdf, tmp_path):
    attempts = []

    def page2(prompt):
        attempts.append(prompt)
        full = page_text_layer(report_pdf, 2)
        return full if len(attempts) > 1 else full.split("Impact:")[0]  # first try drops the second half

    backend = perfect_model(report_pdf, {"transcribe page 2 of 3": page2})
    result = run(report_pdf, tmp_path, backend)
    page = result.meta["pass1_pages"][1]
    assert page["attempts"] == 2 and page["recall"] == 1.0
    assert "were missing" in attempts[1] and "unencrypted" in attempts[1]
    assert result.status == "ok"


def test_page_that_stays_incomplete_needs_review(report_pdf, tmp_path):
    short = lambda prompt: page_text_layer(report_pdf, 2)[:40]  # noqa: E731
    result = run(report_pdf, tmp_path, perfect_model(report_pdf, {"transcribe page 2 of 3": short}))
    assert result.meta["pass1_pages"][1]["attempts"] == 3
    assert result.status == "needs_review"


def test_vision_failure_falls_back_to_text_layer_and_is_flagged(report_pdf, tmp_path):
    fail = lambda prompt: BackendError("GPU out of memory")  # noqa: E731
    result = run(report_pdf, tmp_path, perfect_model(report_pdf, {"transcribe page 1 of 3": fail}))
    assert result.meta["pass1_pages"][0]["source"] == "text_layer_fallback"
    assert result.status == "fallback"
    assert "Report Release Date" in result.transcript_path.read_text(encoding="utf-8")


def test_invalid_structuring_output_is_repaired(report_pdf, tmp_path):
    replies = iter(["not json", json.dumps(SECTION_REPLIES["extract the appendices"])])
    backend = perfect_model(report_pdf, {"extract the appendices": lambda p: next(replies)})
    result = run(report_pdf, tmp_path, backend)
    appendices = next(s for s in result.meta["pass2_sections"] if s["name"] == "appendices")
    assert appendices["source"] == "model" and appendices["attempts"] == 2
    repair_prompt = [c["prompt"] for c in backend.calls if "TASK: extract the appendices" in c["prompt"]][1]
    assert "did not match the required structure" in repair_prompt


def test_unrepairable_section_falls_back_to_rule_based_and_is_flagged(report_pdf, tmp_path):
    result = run(report_pdf, tmp_path, perfect_model(report_pdf, {"extract the front matter": "{}"}))
    front = next(s for s in result.meta["pass2_sections"] if s["name"] == "front matter")
    assert front["source"] == "rule_based"
    assert result.status == "fallback"
    # The rule-based parser still reads the real values from the transcript.
    assert result.data["report_meta"]["report_release_date"] == "2026-02-16"


def test_truncated_output_is_retried(report_pdf, tmp_path):
    replies = iter([Generation(text='{"appendices": {', truncated=True),
                    json.dumps(SECTION_REPLIES["extract the appendices"])])
    result = run(report_pdf, tmp_path, perfect_model(report_pdf, {"extract the appendices": lambda p: next(replies)}))
    appendices = next(s for s in result.meta["pass2_sections"] if s["name"] == "appendices")
    assert appendices["attempts"] == 2 and "token limit" in appendices["issues"][0]


def test_unavailable_model_produces_flagged_fallback(report_pdf, tmp_path, monkeypatch):
    def unavailable(key):
        raise BackendError("no server configured")
    monkeypatch.setattr(pipeline_mod, "create_backend", unavailable)
    pipe = DocumentPipeline(storage=LocalDeepStorage(tmp_path / "store"))
    result = pipe.process_file(report_pdf, tmp_path / "out")
    assert result.status == "fallback"
    assert result.warnings[0].startswith("MODEL PIPELINE FAILED")
    assert [o["title"] for o in result.data["detailed_observations"]] == ["Broken Authentication",
                                                                         "Business Logic Failure"]


def test_docx_is_scanned_before_conversion_and_pdf_after(tmp_path, monkeypatch, report_pdf):
    order = []
    real_gate = gate_mod.malware_gate

    def gate(path, *a, **k):
        order.append(("gate", str(path).rsplit(".", 1)[-1]))
        return real_gate(path, *a, **k)

    def convert(src, out_dir):
        order.append(("convert", src.suffix))
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "report.pdf"
        target.write_bytes(report_pdf.read_bytes())
        return target

    docx = tmp_path / "report.docx"
    from conftest import make_docx
    make_docx(docx, {})
    monkeypatch.setattr(pipeline_mod, "malware_gate", gate)
    monkeypatch.setattr(pipeline_mod, "docx_to_pdf", convert)
    result = run(docx, tmp_path, perfect_model(report_pdf))
    assert order == [("gate", "docx"), ("convert", ".docx"), ("gate", "pdf")]
    assert result.meta["security_gate_converted_pdf"]["verdict"] == "CLEAN"


def test_blocked_docx_is_never_converted(tmp_path, monkeypatch):
    from conftest import make_docx
    OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    docx = make_docx(tmp_path / "macro.docx", {"word/vbaProject.bin": OLE + b"\x00" * 64 + b"_VBA_PROJECT"})
    monkeypatch.setattr(pipeline_mod, "docx_to_pdf", lambda *a: pytest.fail("converter must not run"))
    with pytest.raises(DocumentBlocked):
        run(docx, tmp_path, FakeBackend(lambda *a: ""))


def test_gate_unavailable_refuses_to_process(tmp_path, monkeypatch, report_pdf):
    def unavailable(path, rules=None):
        raise gate_mod.GateUnavailableError("no yara")
    monkeypatch.setattr(gate_mod, "scan_file", unavailable)
    with pytest.raises(PipelineError, match="refusing"):
        run(report_pdf, tmp_path, FakeBackend(lambda *a: ""))


def test_cancel_stops_the_run(report_pdf, tmp_path):
    calls = []
    pipe = DocumentPipeline(backend=perfect_model(report_pdf), storage=LocalDeepStorage(tmp_path / "s"))
    with pytest.raises(PipelineCancelled):
        pipe.process_file(report_pdf, tmp_path / "out", cancel=lambda: calls.append(1) or len(calls) > 4)


def test_rejects_unsupported_and_missing_files(tmp_path):
    (tmp_path / "notes.txt").write_text("x")
    pipe = DocumentPipeline(backend=FakeBackend(lambda *a: ""))
    with pytest.raises(PipelineError, match="Unsupported"):
        pipe.process_file(tmp_path / "notes.txt", tmp_path)
    with pytest.raises(PipelineError, match="not found"):
        pipe.process_file(tmp_path / "missing.pdf", tmp_path)


def test_safe_stem():
    assert safe_stem("best report ") == "best_report"
    assert safe_stem("...") == "document"
