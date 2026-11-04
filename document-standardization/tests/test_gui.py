"""GUI smoke tests: drive the real window through a run with a scripted model."""

import gc
import time
import tkinter as tk

import pytest

from report_to_json import gui as gui_mod
from report_to_json.backends import BackendError
from report_to_json.pipeline import DocumentPipeline
from report_to_json.storage import LocalDeepStorage

from test_pipeline import perfect_model


@pytest.fixture(scope="module")
def _window():
    # One window for the module: repeatedly creating Tk interpreters is flaky on some Windows builds.
    try:
        window = gui_mod.ReportToJsonApp()
    except tk.TclError as exc:  # no display available
        pytest.skip(f"Tk unavailable: {exc}")
    window.withdraw()
    yield window
    window.destroy()
    gc.collect()  # collect Tk variables here, not later on some worker thread


@pytest.fixture
def app(_window):
    _window._pipelines = {}  # each test injects its own backend
    _window._result = None
    return _window


def _use_backend(monkeypatch, tmp_path, backend):
    def factory(model):
        return DocumentPipeline(model=model, backend=backend, storage=LocalDeepStorage(tmp_path / "store"))
    monkeypatch.setattr(gui_mod, "DocumentPipeline", factory)


def _run(app, pdf, tmp_path, timeout=60):
    app._output_dir.set(str(tmp_path / "out"))
    app._set_selected_file(str(pdf))
    app._start_processing()
    deadline = time.time() + timeout
    while app._worker is not None and time.time() < deadline:
        app.update()
        time.sleep(0.02)
    app.update()
    assert app._worker is None, "pipeline did not finish"


def test_model_panel_shows_the_one_model_and_no_picker(app):
    assert app.model_name_lbl.cget("text") == gui_mod.MODEL.label
    assert "Qwen3-VL 4B Instruct AWQ" in gui_mod.MODEL.label
    assert not hasattr(app, "engine_combo")


def test_successful_run_renders_findings(app, report_pdf, tmp_path, monkeypatch):
    monkeypatch.setenv("COVERAGE_THRESHOLD", "0.8")
    _use_backend(monkeypatch, tmp_path, perfect_model(report_pdf))
    _run(app, report_pdf, tmp_path)

    assert app._result.status == "ok"
    assert app.header_status.cget("text").startswith("Complete")
    assert app.kpi_findings.cget("text") == "2 findings"
    cards = app.findings_frame.winfo_children()
    labels = [w.cget("text") for card in cards for w in card.winfo_children()[0].winfo_children()]
    assert any("Broken Authentication" in text for text in labels)


def test_fallback_run_is_shown_as_failure(app, report_pdf, tmp_path, monkeypatch):
    fail = lambda prompt: BackendError("server down")  # noqa: E731
    overrides = {t: fail for t in ("extract the front matter", "extract the scope, team and tools")}
    _use_backend(monkeypatch, tmp_path, perfect_model(report_pdf, overrides))
    _run(app, report_pdf, tmp_path)

    assert app._result.status == "fallback"
    assert "FAILED" in app.header_status.cget("text")
    assert app.header_status.cget("fg") == gui_mod.ROSE


def test_toggling_the_gate_keeps_the_loaded_pipeline(app):
    first = app._pipeline()
    app._enable_gate.set(False)
    try:
        second = app._pipeline()
        assert second is first and second.enable_security_gate is False
    finally:
        app._enable_gate.set(True)
