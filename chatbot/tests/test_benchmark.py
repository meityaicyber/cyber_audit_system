"""The model benchmark: config, question generation, grading and the report."""

from __future__ import annotations

import json
from types import SimpleNamespace

import benchmark_models as bench
import pytest
from conftest import FakeLLM, make_app


def answer(text="", abstained=False, reason="", cited=()):
    return SimpleNamespace(text=text, abstained=abstained, abstention_reason=reason,
                           citations=[SimpleNamespace(chunk_id=c) for c in cited])


def test_grading():
    count = {"type": "count", "expected_contains": [12]}
    assert bench.grade(count, answer("There are 12 findings."), []) is True
    assert bench.grade(count, answer("There are 112 findings."), []) is False   # whole number only
    assert bench.grade(count, answer("12", abstained=True), []) is False

    assert bench.grade({"type": "lookup"}, answer("x", cited=["a"]), ["a", "b"]) is True
    assert bench.grade({"type": "lookup"}, answer("x", cited=["c"]), ["a", "b"]) is False
    assert bench.grade({"type": "lookup"}, answer("x"), []) is None             # no label

    refuse = {"type": "unanswerable"}
    assert bench.grade(refuse, answer(abstained=True), []) is True
    assert bench.grade(refuse, answer("Made up."), []) is False
    assert bench.grade(refuse, answer("The report does not say."), []) is True
    assert bench.grade(refuse, answer("It does not say, but see", cited=["a"]), []) is False
    # A dead backend abstains on everything; it must not score as honest refusal.
    assert bench.grade(refuse, answer(abstained=True, reason="llm_unavailable"), []) is False


def test_a_missing_local_path_is_not_a_repo_id():
    assert bench.model_spec("E:/no/such/model")["repo_id"] == ""


def test_config_shorthand_and_environment(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"corpus": "sample_data", "defaults": {"settings": {"RAGAUDIT_X": 1}}, "runs": [
        {"chat": "nemotron", "embedding": "BAAI/bge-m3", "reranker": None},
        {"name": "two", "chat": "qwen3:8b", "embedding": "BAAI/bge-m3", "reranker": "BAAI/bge-reranker-v2-m3"},
        {"name": "three", "chat": None, "embedding": "Qwen/Qwen3-Embedding-0.6B"},
    ]}), encoding="utf-8")
    config = bench.load_config(path)
    one, two, three = config["runs"]
    assert one["embedding"] == {"repo_id": "BAAI/bge-m3", "model_path": "models/bge-m3"}

    env = bench.run_env(config, two)
    assert env["RAGAUDIT_GENERATION__MODEL_NAME"] == "qwen3:8b"
    assert env["RAGAUDIT_RERANKER__MODEL_PATH"] == "models/bge-reranker-v2-m3"
    assert env["RAGAUDIT_RETRIEVAL__BACKEND"] == "numpy"      # never the live Postgres index
    assert env["RAGAUDIT_X"] == "1"
    assert "bench" in env["RAGAUDIT_CATALOG_PATH"]            # never the live catalogue
    assert bench.run_env(config, one)["RAGAUDIT_RERANKER__ENABLED"] == "false"

    assert bench.store_dir(config, one) == bench.store_dir(config, two)     # embedding reused
    assert bench.store_dir(config, one) != bench.store_dir(config, three)


def test_lists_at_the_top_expand_to_every_combination(monkeypatch):
    monkeypatch.setattr(bench, "CHAT_MODELS", ["nemotron-mini", "qwen3:8b", None])
    monkeypatch.setattr(bench, "EMBEDDING_MODELS", ["BAAI/bge-m3", "x/emb"])
    monkeypatch.setattr(bench, "RERANKERS", ["BAAI/bge-reranker-v2-m3", None])
    runs = bench.prepare_config(bench.config_from_lists())["runs"]
    assert len(runs) == 12 and len({r["name"] for r in runs}) == 12
    assert runs[0]["name"] == "nemotron-mini+bge-m3+bge-reranker-v2-m3"
    assert runs[0]["settings"] == bench.SETTINGS
    assert runs[-1]["chat"] is None and runs[-1]["reranker"] is None


def test_duplicate_run_names_are_refused(tmp_path):
    path = tmp_path / "c.json"
    run = {"name": "a", "embedding": "x/y"}
    path.write_text(json.dumps({"corpus": "c", "runs": [run, run]}), encoding="utf-8")
    with pytest.raises(SystemExit):
        bench.load_config(path)


def test_questions_from_the_catalogue_have_true_answers(app):
    questions = bench.generate_questions(app.catalog, n_lookup=3)
    kinds = {q["type"] for q in questions}
    assert kinds == {"count", "lookup", "unanswerable"}
    assert questions == bench.generate_questions(app.catalog, n_lookup=3)   # same set every time
    high = next(q for q in questions if q["text"] == "How many High severity findings are there?")
    assert high["expected_contains"] == [app.catalog.count_findings(severities=["High"])]
    lookups = [q for q in questions if q["type"] == "lookup"]
    assert len(lookups) == 3 and all(bench.gold_chunks(app.catalog, q) for q in lookups)


def test_scoring_through_the_real_pipeline(tmp_path, corpus):
    app = make_app(tmp_path, llm=FakeLLM())
    assert bench.ingest(app, corpus, None)["indexed"] == 2
    questions = bench.generate_questions(app.catalog, n_lookup=4)
    for i, q in enumerate(questions):
        q["id"] = f"Q{i}"

    retrieval = bench.score_retrieval(app, questions)
    assert retrieval["n"] == 4 and retrieval["hit"] > 0

    chat, rows = bench.score_chat(app, questions)
    assert len(rows) == len(questions) and chat["graded"] == len(questions)
    assert chat["by_type"]["count"] == 1.0
    app.close()


def test_max_reports_limits_the_corpus(tmp_path, corpus):
    app = make_app(tmp_path)
    bench.ingest(app, corpus, 1)
    assert len(app.catalog.reports_overview()) == 1
    app.close()


def _result(name, accuracy):
    return {"name": name, "status": "ok", "chat": "m", "embedding": "models/e", "reranker": None,
            "ingest": {"seconds": 1.0}, "retrieval": {"recall": 0.5, "hit": 0.5, "mrr": 0.5, "ndcg": 0.5, "mean_ms": 9.0},
            "chat_metrics": {"accuracy": accuracy, "graded": 2, "by_type": {"count": accuracy},
                             "grounding": {"citation_rate": 1.0, "fabricated_citations": 0, "fabricated_quotes": 1},
                             "mean_s": 1.0, "p95_s": 2.0, "backend_failures": 0}}


def test_report_ranks_runs_and_keeps_failures(tmp_path):
    for name, correct in (("good", [True, True]), ("bad", [False, True])):
        (tmp_path / name).mkdir()
        (tmp_path / name / "questions.json").write_text(json.dumps(
            [{"id": f"Q{i}", "correct": c} for i, c in enumerate(correct)]), encoding="utf-8")
    failed = {"name": "broke", "status": "failed", "error": "out of memory", "chat": "m",
              "embedding": "models/e", "reranker": None}

    report = bench.compare([_result("bad", 0.5), failed, _result("good", 1.0)], tmp_path).read_text(encoding="utf-8")
    assert report.index("| good |") < report.index("| bad |") < report.index("| broke |")
    assert "broke failed: out of memory" in report
    assert "- bad:" in report                                 # paired test against the top run
    assert (tmp_path / "comparison.csv").exists()


def test_a_failing_run_does_not_stop_the_others(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "BENCH_DIR", tmp_path)
    run = {"name": "x", "chat": None, "embedding": {"repo_id": "", "model_path": str(tmp_path / "none")}, "reranker": None}
    config = {"corpus": str(tmp_path), "runs": [run]}
    result = bench.run_one(config, run, tmp_path / "out", tmp_path / "q.json", "http://127.0.0.1:1")
    assert result["status"] == "failed" and "no weights" in result["error"]


def test_missing_chat_model_is_pulled_over_http(monkeypatch):
    calls = []

    def fake(base, path, body=None, timeout=30):
        calls.append(path)
        return {"models": []} if path == "/api/tags" else {"capabilities": ["tools"]}

    monkeypatch.setattr(bench, "_ollama", fake)
    assert bench.prepare_chat("http://ollama:11434", "nemotron-mini") == []
    assert calls == ["/api/tags", "/api/pull", "/api/show"]
