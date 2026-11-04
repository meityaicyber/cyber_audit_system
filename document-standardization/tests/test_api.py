"""The integration function: report path in, the standardised JSON (as text) out."""

import json

import pytest

import report_to_json
from report_to_json import api, schema
from report_to_json.backends import BackendError
from report_to_json.pipeline import DocumentBlocked, DocumentPipeline, PipelineError
from report_to_json.storage import LocalDeepStorage

from conftest import FakeBackend, make_docx
from test_pipeline import perfect_model


@pytest.fixture
def use_backend(monkeypatch, tmp_path):
    """Make the API build its pipeline around a scripted model."""
    created = []

    def install(backend):
        def factory():
            created.append(1)
            return DocumentPipeline(backend=backend, storage=LocalDeepStorage(tmp_path / "store"))
        monkeypatch.setattr(api, "DocumentPipeline", factory)
        monkeypatch.setattr(api, "_pipeline", None)
        return created

    monkeypatch.setenv("COVERAGE_THRESHOLD", "0.8")
    return install


def test_returns_the_json_for_a_report(report_pdf, tmp_path, use_backend):
    use_backend(perfect_model(report_pdf))
    response = report_to_json.standardize_report(report_pdf, tmp_path / "out")

    assert isinstance(response, str)
    data = json.loads(response)
    assert set(data) == set(schema.template())  # the master schema and nothing else
    assert schema.validate(data) == []
    assert [o["title"] for o in data["detailed_observations"]] == ["Broken Authentication", "Business Logic Failure"]
    # The response is the output: byte-for-byte the saved JSON file.
    assert response == (tmp_path / "out" / "acme-report.json").read_text(encoding="utf-8")
    assert (tmp_path / "out" / "acme-report.meta.json").exists()


def test_accepts_string_paths_and_reuses_the_pipeline(report_pdf, tmp_path, use_backend):
    created = use_backend(perfect_model(report_pdf))
    first = api.standardize_report(str(report_pdf), str(tmp_path / "out"))
    second = api.standardize_report(str(report_pdf), str(tmp_path / "out"))
    assert first == second
    assert created == [1]  # the model is set up once per process


def test_fallback_output_is_still_returned_with_a_warning(report_pdf, tmp_path, use_backend, caplog):
    use_backend(FakeBackend(lambda *a: BackendError("server down")))
    with caplog.at_level("WARNING", logger="report_to_json.api"):
        data = json.loads(api.standardize_report(report_pdf, tmp_path / "out"))
    assert set(data) == set(schema.template())
    assert len(data["detailed_observations"]) == 2  # the rule-based parser's result
    assert "model pipeline failed" in caplog.text
    run_report = json.loads((tmp_path / "out" / "acme-report.meta.json").read_text(encoding="utf-8"))
    assert run_report["status"] == "fallback"


def test_strict_mode_raises_on_fallback(report_pdf, tmp_path, use_backend):
    use_backend(FakeBackend(lambda *a: BackendError("server down")))
    with pytest.raises(api.ModelPipelineFailed) as exc:
        api.standardize_report(report_pdf, tmp_path / "out", strict=True)
    assert exc.value.result.status == "fallback"
    assert "fell back" in str(exc.value)


def test_process_report_returns_status_and_run_report(report_pdf, tmp_path, use_backend):
    use_backend(perfect_model(report_pdf))
    result = api.process_report(report_pdf, tmp_path / "out")
    assert result.status == "ok"
    assert result.meta["model"]["key"] == "qwen3-vl-4b-instruct-awq"
    assert result.data == json.loads(result.json_path.read_text(encoding="utf-8"))


def test_blocked_and_invalid_inputs_raise(tmp_path, use_backend):
    use_backend(FakeBackend(lambda *a: ""))
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    macro = make_docx(tmp_path / "macro.docx", {"word/vbaProject.bin": ole + b"\x00" * 64 + b"_VBA_PROJECT"})
    with pytest.raises(DocumentBlocked):
        api.standardize_report(macro, tmp_path / "out")
    with pytest.raises(PipelineError, match="not found"):
        api.standardize_report(tmp_path / "missing.pdf", tmp_path / "out")


def test_package_exports_the_entry_points():
    assert report_to_json.standardize_report is api.standardize_report
    assert report_to_json.process_report is api.process_report
    assert issubclass(report_to_json.ModelPipelineFailed, PipelineError)
