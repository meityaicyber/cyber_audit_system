#!/usr/bin/env python3
"""Compare model combinations on the whole RAG pipeline.

Edit the lists under "EDIT HERE" below, then:

    python benchmark_models.py                     # every combination of the lists
    python benchmark_models.py --only NAME         # one run
    python benchmark_models.py --force             # redo finished runs
    python benchmark_models.py my.json             # exact runs from a file instead
                                                   # (see eval/benchmark.example.json)

For each combination this ingests the corpus, scores retrieval, asks every
question through the real chat service, and writes
var/bench/<name>/comparison.md.

* Live data is not touched: runs use their own stores under var/bench/ with the
  numpy index, never var/index or the Postgres ``rag`` schema.
* Runs sharing an embedding model and corpus share one store, so embedding, the
  slow step, happens once per embedding model.
* Each run is its own process, so a model that crashes or runs out of memory
  fails that run only. Finished runs are skipped, so re-running resumes.
* Everyone answers the same questions: the set is generated from the corpus on
  the first run and reused. Edit the file, or set "questions", to use your own.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from itertools import product
from pathlib import Path
from typing import Any

# ==========================================================================
# EDIT HERE
# ==========================================================================

# Folder or file of report JSON to test on.
CORPUS = "sample_data"

# Use only the first N reports, for a quick try. None = all of them.
MAX_REPORTS = None

# Your own question file. None = generate one from the corpus.
QUESTIONS = None

# How many generated "what is the fix for finding X" questions to ask.
LOOKUP_QUESTIONS = 30

# Chat models: Ollama names, pulled if missing.
# None = skip the chat step and score retrieval only.
CHAT_MODELS = [
    "qwen3:8b",
    # "qwen3:14b",
    # "nemotron-mini",
    # "llama3.1:8b",
    # "mistral-nemo",
]

# Embedding models: Hugging Face repo ids (downloaded to models/ if missing) or local folders.
EMBEDDING_MODELS = [
    "Qwen/Qwen3-Embedding-0.6B",
    # "BAAI/bge-large-en-v1.5",
    # "BAAI/bge-m3",
    # "intfloat/multilingual-e5-large",
]

# Rerankers: Hugging Face repo ids or local folders. None = no reranker.
RERANKERS = [
    "Qwen/Qwen3-Reranker-0.6B",
    # "BAAI/bge-reranker-v2-m3",
    # None,
]

# Any other engine setting, applied to every run.
SETTINGS = {
    "RAGAUDIT_AGENT__DEADLINE_S": "300",       # slow models need longer than the default 90
    "RAGAUDIT_AGENT__STEP_TIMEOUT_S": "120",
    "RAGAUDIT_GENERATION__TIMEOUT_S": "180",
}

# ==========================================================================

ROOT = Path(__file__).resolve().parent
BENCH_DIR = ROOT / "var" / "bench"

#: Nothing in an audit report answers these, so the correct behaviour is to refuse.
UNANSWERABLE = [
    "What was the annual salary of the chief auditor?",
    "Which football team sponsored the audit?",
    "What is the street address of the auditor's cafeteria?",
    "How many employees attended the office picnic?",
    "What was the weather on the day of the audit?",
]


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


def model_spec(value: Any) -> dict | None:
    """"org/model", a local folder, or {"repo_id":..., "model_path":...}. None disables it."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {"repo_id": value.get("repo_id", ""),
                "model_path": value.get("model_path") or f"models/{value['repo_id'].split('/')[-1]}"}
    if Path(value).is_absolute() or Path(value).exists() or (ROOT / value).exists():
        return {"repo_id": "", "model_path": str(value)}
    return {"repo_id": value, "model_path": f"models/{value.split('/')[-1]}"}


def config_from_lists() -> dict:
    """Every combination of the lists above. Embedding is the outer loop, so
    runs sharing an embedder sit together."""
    runs = [{"chat": chat, "embedding": embedding, "reranker": reranker}
            for embedding, reranker, chat in product(EMBEDDING_MODELS, RERANKERS, CHAT_MODELS)]
    return {"corpus": CORPUS, "max_reports": MAX_REPORTS, "questions": QUESTIONS,
            "lookup_questions": LOOKUP_QUESTIONS, "defaults": {"settings": SETTINGS}, "runs": runs}


def load_config(path: Path) -> dict:
    return prepare_config(json.loads(Path(path).read_text(encoding="utf-8")))


def prepare_config(config: dict) -> dict:
    if not config.get("corpus") or not config.get("runs"):
        raise SystemExit("config needs \"corpus\" and a non-empty \"runs\" list")
    defaults = config.get("defaults", {})
    names = set()
    runs = []
    for raw in config["runs"]:
        run = {**defaults, **raw}
        if not run.get("embedding"):
            raise SystemExit(f"run {raw} has no \"embedding\"")
        run["name"] = run.get("name") or "+".join(
            Path(str(run.get(k) or "none")).name for k in ("chat", "embedding", "reranker"))
        if run["name"] in names:
            raise SystemExit(f"two runs are named {run['name']!r}")
        names.add(run["name"])
        run["embedding"] = model_spec(run["embedding"])
        run["reranker"] = model_spec(run.get("reranker"))
        runs.append(run)
    config["runs"] = runs
    return config


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")


def store_dir(config: dict, run: dict) -> Path:
    """One store per embedding model and corpus."""
    key = f"{config['corpus']}|{config.get('max_reports')}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return BENCH_DIR / "stores" / f"{slug(Path(run['embedding']['model_path']).name)}-{digest}"


def run_env(config: dict, run: dict) -> dict[str, str]:
    """Environment for one run. These override .env, so the live setup stays out of it."""
    store = store_dir(config, run)
    env = {
        **os.environ,
        "RAGAUDIT_DATA_DIR": str(store),
        "RAGAUDIT_CATALOG_PATH": str(store / "catalog.sqlite3"),
        "RAGAUDIT_INDEX_DIR": str(store / "index"),
        "RAGAUDIT_FIGURE_DIR": str(store / "figures"),
        "RAGAUDIT_RETRIEVAL__BACKEND": "numpy",
        "RAGAUDIT_EMBEDDING__REPO_ID": run["embedding"]["repo_id"],
        "RAGAUDIT_EMBEDDING__MODEL_PATH": run["embedding"]["model_path"],
        "RAGAUDIT_RERANKER__ENABLED": "true" if run["reranker"] else "false",
    }
    if run["reranker"]:
        env["RAGAUDIT_RERANKER__REPO_ID"] = run["reranker"]["repo_id"]
        env["RAGAUDIT_RERANKER__MODEL_PATH"] = run["reranker"]["model_path"]
    if run.get("chat"):
        env["RAGAUDIT_GENERATION__MODEL_NAME"] = run["chat"]
    # Any other setting, e.g. {"RAGAUDIT_AGENT__DEADLINE_S": "300"}, per run or in defaults.
    env.update({k: str(v) for k, v in (run.get("settings") or {}).items()})
    return env


# --------------------------------------------------------------------------
# Questions and grading
# --------------------------------------------------------------------------


def generate_questions(catalog, n_lookup: int = 30, seed: int = 42) -> list[dict]:
    """A labelled set built from the catalogue, so no hand labelling is needed.

    Counts come from SQL, so their answers are exact. Lookups ask about a
    sampled finding by title, which favours keyword search: hand-written,
    paraphrased questions test embeddings harder, so add some when you can.
    """
    questions: list[dict] = []
    for severity, n in catalog.severity_breakdown().items():
        if n and severity != "Unknown":
            questions.append({"type": "count", "text": f"How many {severity} severity findings are there?",
                              "expected_contains": [n]})
    for status, n in catalog.status_breakdown().items():
        if n and status != "Unknown":
            questions.append({"type": "count", "text": f"How many findings have the status {status}?",
                              "expected_contains": [n]})
    for cwe, n in list(catalog.value_counts("cwe").items())[:5]:
        questions.append({"type": "count", "text": f"How many findings cite {cwe}?", "expected_contains": [n]})

    findings = [f for f in catalog.findings() if f.title and f.recommendation]
    by_title: dict[str, list] = {}
    for f in findings:
        by_title.setdefault(f.title.strip().lower(), []).append(f)
    titles = sorted(by_title)
    random.Random(seed).shuffle(titles)
    for title in titles[:n_lookup]:
        group = by_title[title]
        questions.append({
            "type": "lookup",
            "text": f"What is the recommended fix for the finding '{group[0].title}'?",
            "gold_findings": [[f.report_id, f.finding_id] for f in group],
        })

    questions += [{"type": "unanswerable", "text": text} for text in UNANSWERABLE]
    for i, q in enumerate(questions, start=1):
        q["id"] = f"Q{i:03d}"
    return questions


_REFUSAL_RE = re.compile(r"\b(does not|doesn't|do not|not) (say|state|explicitly|mention|cover|contain|provide)"
                         r"|\bno information\b|\bnot (covered|mentioned|available)\b", re.I)


def gold_chunks(catalog, question: dict) -> list[str]:
    ids = list(question.get("gold_chunk_ids") or [])
    for report_id, finding_id in question.get("gold_findings") or []:
        ids += [r["chunk_id"] for r in catalog.chunks_for_finding(finding_id, [report_id])]
    return ids


def grade(question: dict, answer, gold: list[str]) -> bool | None:
    """True or False, or None when the question carries no label."""
    if answer.abstention_reason == "llm_unavailable":
        return False                          # a dead backend is not a correct refusal
    if question.get("type") == "unanswerable":
        # A model can refuse in words without setting the abstained flag.
        return answer.abstained or (not answer.citations and bool(_REFUSAL_RE.search(answer.text)))
    if question.get("expected_contains"):
        return not answer.abstained and all(
            re.search(rf"(?<![\d.]){re.escape(str(v))}(?!\d)", answer.text)
            for v in question["expected_contains"])
    if gold:
        return not answer.abstained and any(c.chunk_id in gold for c in answer.citations)
    return None


# --------------------------------------------------------------------------
# One run (child process)
# --------------------------------------------------------------------------


def ingest(app, corpus: Path, max_reports: int | None) -> dict:
    from ragaudit.ingest.pipeline import discover_reports

    paths = [corpus] if corpus.is_file() else sorted(discover_reports(corpus))
    if max_reports:
        paths = paths[:max_reports]
    started = time.perf_counter()
    summary = app.build_ingest().ingest_paths(paths).summary()
    return {"seconds": round(time.perf_counter() - started, 1), **summary}


def score_retrieval(app, questions: list[dict], k: int = 5) -> dict:
    from ragaudit.eval.metrics import hit_rate_at_k, ndcg_at_k, recall_at_k, reciprocal_rank

    retriever = app.build_retriever()
    rows, times = [], []
    for q in questions:
        gold = gold_chunks(app.catalog, q)
        if not gold:
            continue
        scope = [q["report_id"]] if q.get("report_id") else None
        started = time.perf_counter()
        hits = retriever.retrieve(q["text"], report_ids=scope, top_k=k)
        times.append((time.perf_counter() - started) * 1000)
        ids = [h.chunk.chunk_id for h in hits]
        rows.append({"hit": hit_rate_at_k(ids, gold, k), "recall": recall_at_k(ids, gold, k) or 0.0,
                     "mrr": reciprocal_rank(ids, gold), "ndcg": ndcg_at_k(ids, gold, k)})
    if not rows:
        return {"n": 0}
    out: dict[str, Any] = {key: round(statistics.mean(r[key] for r in rows), 4) for key in rows[0]}
    return {**out, "n": len(rows), "k": k, "mean_ms": round(statistics.mean(times), 1)}


def score_chat(app, questions: list[dict]) -> tuple[dict, list[dict]]:
    from ragaudit.eval.metrics import grounding_report

    answers, rows = [], []
    for q in questions:
        chat = app.build_chat()                      # a fresh session: no carry-over between questions
        scope = [q["report_id"]] if q.get("report_id") else None
        answer, _ = chat.ask(q["text"], report_ids=scope)
        answers.append(answer)
        rows.append({
            "id": q["id"], "type": q.get("type", ""), "question": q["text"],
            "correct": grade(q, answer, gold_chunks(app.catalog, q)),
            "answer": answer.text, "abstained": answer.abstained, "reason": answer.abstention_reason,
            "citations": [c.chunk_id for c in answer.citations], "tools": [s["tool"] for s in answer.steps],
            "flags": answer.review_flags, "latency_s": round(answer.latency_s, 2),
        })

    graded = [r for r in rows if r["correct"] is not None]
    by_type: dict[str, list] = {}
    for r in graded:
        by_type.setdefault(r["type"] or "other", []).append(r["correct"])
    latencies = sorted(r["latency_s"] for r in rows)
    return {
        "accuracy": round(sum(r["correct"] for r in graded) / len(graded), 4) if graded else None,
        "graded": len(graded),
        "by_type": {t: round(sum(v) / len(v), 4) for t, v in by_type.items()},
        "grounding": grounding_report(answers).to_dict(),
        "mean_s": round(statistics.mean(latencies), 2),
        "p95_s": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
        "backend_failures": sum(1 for r in rows if r["reason"] == "llm_unavailable"),
    }, rows


def ensure_weights(spec: dict | None) -> None:
    if spec is None:
        return
    path = Path(spec["model_path"])
    path = path if path.is_absolute() else ROOT / path
    if (path / "config.json").exists():
        return
    if not spec["repo_id"]:
        raise RuntimeError(f"no weights at {path}, and no repo_id to download them from")
    from huggingface_hub import snapshot_download

    print(f"downloading {spec['repo_id']} -> {path}", flush=True)
    snapshot_download(repo_id=spec["repo_id"], local_dir=str(path))


def worker(job_path: Path) -> int:
    from ragaudit.app import Application
    from ragaudit.config import load_settings

    job = json.loads(job_path.read_text(encoding="utf-8"))
    run, out = job["run"], Path(job["out"])
    ensure_weights(run["embedding"])
    ensure_weights(run["reranker"])

    app = Application(load_settings(log_level="WARNING"), configure_logs=False)
    try:
        ingested = ingest(app, Path(job["corpus"]), job.get("max_reports"))
        print(f"ingest: {ingested}", flush=True)

        questions_path = Path(job["questions"])
        if not questions_path.exists():
            questions_path.parent.mkdir(parents=True, exist_ok=True)
            questions_path.write_text(json.dumps(
                generate_questions(app.catalog, job.get("lookup_questions", 30)), indent=2), encoding="utf-8")
        questions = json.loads(questions_path.read_text(encoding="utf-8"))
        for i, q in enumerate(questions, start=1):
            q.setdefault("id", f"Q{i:03d}")

        retrieval = score_retrieval(app, questions)
        print(f"retrieval: {retrieval}", flush=True)
        chat, rows = (score_chat(app, questions) if run.get("chat") else ({}, []))
        print(f"chat: {chat}", flush=True)

        (out / "questions.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        (out / "result.json").write_text(json.dumps({
            "name": run["name"], "status": "ok", "chat": run.get("chat"),
            "embedding": run["embedding"]["model_path"],
            "reranker": run["reranker"]["model_path"] if run["reranker"] else None,
            "ingest": ingested, "retrieval": retrieval, "chat_metrics": chat,
            "notes": job.get("notes", []),
        }, indent=2), encoding="utf-8")
        return 0
    finally:
        app.close()


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def _ollama(base: str, path: str, body: dict | None = None, timeout: float = 30) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(base + path, data, {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def prepare_chat(base: str, model: str) -> list[str]:
    """Pull the chat model if missing. Returns notes for the report."""
    try:
        have = [m.get("name") for m in _ollama(base, "/api/tags").get("models", [])]
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Ollama is not reachable at {base}: {exc}") from exc
    if model not in have and f"{model}:latest" not in have:
        print(f"pulling {model} ...", flush=True)
        # Over HTTP: inside Docker the Ollama server is on the host and there is no CLI.
        try:
            _ollama(base, "/api/pull", {"model": model, "stream": False}, timeout=3600)
        except (urllib.error.URLError, OSError) as exc:
            raise RuntimeError(f"could not pull {model}: {exc}") from exc
    capabilities = _ollama(base, "/api/show", {"model": model}).get("capabilities") or []
    if capabilities and "tools" not in capabilities:
        return [f"{model} has no tool calling: answers come from the single-pass fallback, not the agent"]
    return []


def unload_chat(base: str, model: str) -> None:
    """Free the model's memory before the next run loads another."""
    try:
        _ollama(base, "/api/generate", {"model": model, "keep_alive": 0})
    except (urllib.error.URLError, OSError):
        pass


def run_one(config: dict, run: dict, out_root: Path, questions: Path, base: str) -> dict:
    out = out_root / slug(run["name"])
    out.mkdir(parents=True, exist_ok=True)
    log = out / "run.log"
    print(f"\n=== {run['name']} ===", flush=True)
    try:
        notes = prepare_chat(base, run["chat"]) if run.get("chat") else []
    except RuntimeError as exc:
        return failed(run, str(exc))

    job = out / "job.json"
    job.write_text(json.dumps({
        "run": run, "out": str(out), "corpus": str(Path(config["corpus"]).resolve()),
        "questions": str(questions), "max_reports": config.get("max_reports"),
        "lookup_questions": config.get("lookup_questions", 30), "notes": notes,
    }), encoding="utf-8")
    started = time.perf_counter()
    with log.open("w", encoding="utf-8") as handle:
        code = subprocess.call([sys.executable, str(Path(__file__).resolve()), "--worker", str(job)],
                               env=run_env(config, run), cwd=str(ROOT), stdout=handle, stderr=subprocess.STDOUT)
    if run.get("chat"):
        unload_chat(base, run["chat"])
    result_path = out / "result.json"
    if code or not result_path.exists():
        tail = log.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-1:] or ["no output"]
        return failed(run, f"exit {code}: {tail[0][:200]} (see {log})")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    print(f"done in {time.perf_counter() - started:.0f}s", flush=True)
    return result


def failed(run: dict, error: str) -> dict:
    print(f"FAILED: {error}", flush=True)
    return {"name": run["name"], "status": "failed", "error": error, "chat": run.get("chat"),
            "embedding": run["embedding"]["model_path"],
            "reranker": run["reranker"]["model_path"] if run["reranker"] else None}


def compare(results: list[dict], out_root: Path) -> Path:
    """Write comparison.md and comparison.csv, best first."""
    from ragaudit.eval.metrics import mcnemar, minimum_detectable_difference

    def key(r):
        chat, ret = r.get("chat_metrics") or {}, r.get("retrieval") or {}
        return (r["status"] == "ok", chat.get("accuracy") or 0, ret.get("recall") or 0)

    ordered = sorted(results, key=key, reverse=True)
    columns = ["run", "status", "chat", "embedding", "reranker", "accuracy", "count", "lookup", "refusal",
               "citation_rate", "fabricated", "recall@k", "hit@k", "mrr", "ndcg", "retrieval_ms",
               "chat_mean_s", "chat_p95_s", "ingest_s"]
    table = []
    for r in ordered:
        chat, ret = r.get("chat_metrics") or {}, r.get("retrieval") or {}
        by_type, grounding = chat.get("by_type") or {}, chat.get("grounding") or {}
        table.append({
            "run": r["name"], "status": r["status"], "chat": r.get("chat") or "-",
            "embedding": Path(r["embedding"]).name, "reranker": Path(r["reranker"]).name if r.get("reranker") else "-",
            "accuracy": chat.get("accuracy"), "count": by_type.get("count"), "lookup": by_type.get("lookup"),
            "refusal": by_type.get("unanswerable"), "citation_rate": grounding.get("citation_rate"),
            "fabricated": (grounding.get("fabricated_citations", 0) + grounding.get("fabricated_quotes", 0))
            if grounding else None,
            "recall@k": ret.get("recall"), "hit@k": ret.get("hit"), "mrr": ret.get("mrr"), "ndcg": ret.get("ndcg"),
            "retrieval_ms": ret.get("mean_ms"), "chat_mean_s": chat.get("mean_s"), "chat_p95_s": chat.get("p95_s"),
            "ingest_s": (r.get("ingest") or {}).get("seconds"),
        })

    with (out_root / "comparison.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(table)

    def cell(value):
        return "-" if value is None else (f"{value:.3f}" if isinstance(value, float) else str(value))

    lines = ["# Model comparison", "", "| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    lines += ["| " + " | ".join(cell(row[c]) for c in columns) + " |" for row in table]

    best = next((r for r in ordered if r["status"] == "ok" and r.get("chat_metrics")), None)
    if best:
        graded = (best["chat_metrics"].get("graded") or 0)
        lines += ["", f"{graded} graded questions: gaps under about "
                      f"{minimum_detectable_difference(max(graded, 1)):.0%} are not evidence of a real difference."]
        base_rows = _graded(out_root, best)
        others = [r for r in ordered if r is not best and r["status"] == "ok" and r.get("chat_metrics")]
        if others:
            lines += ["", "## Against the top run (McNemar, paired)", ""]
        for other in others:
            rows = _graded(out_root, other)
            common = sorted(set(base_rows) & set(rows))
            result = mcnemar([base_rows[i] for i in common], [rows[i] for i in common])
            lines.append(f"- {other['name']}: {result.verdict(best['name'], other['name'])}")

    problems = [r for r in ordered if r["status"] != "ok"]
    notes = [(r["name"], n) for r in ordered for n in r.get("notes", [])]
    degraded = [r for r in ordered if (r.get("chat_metrics") or {}).get("backend_failures")]
    if problems or notes or degraded:
        lines += ["", "## Problems", ""]
        lines += [f"- {r['name']} failed: {r['error']}" for r in problems]
        lines += [f"- {name}: {note}" for name, note in notes]
        lines += [f"- {r['name']}: model backend failed on {r['chat_metrics']['backend_failures']} question(s)"
                  for r in degraded]

    report = out_root / "comparison.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _graded(out_root: Path, result: dict) -> dict[str, bool]:
    rows = json.loads((out_root / slug(result["name"]) / "questions.json").read_text(encoding="utf-8"))
    return {r["id"]: r["correct"] for r in rows if r["correct"] is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("config", nargs="?", help="JSON file of exact runs; default is the lists at the top")
    parser.add_argument("--only", action="append", help="run only this name (repeatable)")
    parser.add_argument("--force", action="store_true", help="redo runs that already finished")
    parser.add_argument("--worker", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        logging.basicConfig(level=logging.WARNING)
        return worker(Path(args.worker))
    from ragaudit.config import load_settings

    config = load_config(Path(args.config)) if args.config else prepare_config(config_from_lists())
    if not Path(config["corpus"]).exists():
        raise SystemExit(f"corpus not found: {config['corpus']}")
    out_root = BENCH_DIR / (slug(Path(args.config).stem) if args.config else "models")
    out_root.mkdir(parents=True, exist_ok=True)
    questions = Path(config["questions"]).resolve() if config.get("questions") else out_root / "questions.json"
    base = load_settings().generation.base_url.rstrip("/")

    results = []
    for run in config["runs"]:
        done = out_root / slug(run["name"]) / "result.json"
        selected = not args.only or run["name"] in args.only
        if done.exists() and not (args.force and selected):
            results.append(json.loads(done.read_text(encoding="utf-8")))
            print(f"=== {run['name']}: already finished, reusing", flush=True)
        elif selected:
            if done.exists():
                done.unlink()
            results.append(run_one(config, run, out_root, questions, base))

    report = compare(results, out_root)
    print(f"\n{report.read_text(encoding='utf-8')}\nReport: {report}")
    return 0 if all(r["status"] == "ok" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
