#!/usr/bin/env python3
"""Unified One-Click Launcher for Cybersecurity RAG Engine & PostgreSQL Migration.

What this single master script does:
1. Auto-detects virtual environment if running with bare system Python.
2. Verifies/creates PostgreSQL 'report_chunks' table & pgvector HNSW index.
3. Synchronizes/backfills past historical reports from PostgreSQL (reports_data & detailed_observations)
   into PostgreSQL pgvector and local SQLite catalogue (with auto-resume and retry).
4. Checks local LLM (Ollama) and local embedding models.
5. Starts the RAG Web Console & API Server on http://localhost:8077.

Usage:
    python start_rag.py
    python start_rag.py --port 8077
    python start_rag.py --skip-ingest    # Start server immediately without checking past reports
    python start_rag.py --force          # Re-embed all past reports from scratch
"""

from __future__ import annotations

import os
import sys
import subprocess
from pathlib import Path

# --------------------------------------------------------------------------
# 0. Auto-detect and re-exec with venv python if running with system python
# --------------------------------------------------------------------------
CURRENT_FILE = Path(__file__).resolve()
ROOT = CURRENT_FILE.parent

CANDIDATE_VENVS = [
    ROOT / ".venv" / "Scripts" / "python.exe",
    ROOT / "chatbot" / ".venv" / "Scripts" / "python.exe",
    ROOT / "ragengine" / ".venv" / "Scripts" / "python.exe",
    ROOT.parent / "rag" / "ragengine" / ".venv" / "Scripts" / "python.exe",
    Path(r"E:\rag\ragengine\.venv\Scripts\python.exe"),
]

for vpy in CANDIDATE_VENVS:
    if vpy.exists() and sys.executable.lower() != str(vpy).lower():
        cmd = [str(vpy), str(CURRENT_FILE)] + sys.argv[1:]
        sys.exit(subprocess.call(cmd))

ENGINE_DIR = next((ROOT / d for d in ("chatbot", "ragengine") if (ROOT / d / "ragaudit").exists()), ROOT)

if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
os.chdir(str(ENGINE_DIR))

# Load .env safely
try:
    from dotenv import load_dotenv
    load_dotenv(ENGINE_DIR / ".env")
except ImportError:
    pass

import argparse
import asyncio
import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("start_rag")

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:supersecretpassword@localhost:5432/cyber_audit"
).replace("postgresql+asyncpg://", "postgresql://")

TABLE_DDL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS report_chunks (
    chunk_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES reports(report_id) ON DELETE CASCADE,
    section_id VARCHAR(255),
    chunk TEXT NOT NULL,
    embedding vector(1024),
    chunk_index INTEGER,
    context_prefix TEXT,
    finding_id VARCHAR(255),
    token_count INTEGER,
    meta JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_report_chunks_report_id ON report_chunks(report_id);
CREATE INDEX IF NOT EXISTS ix_report_chunks_section_id ON report_chunks(section_id);
CREATE INDEX IF NOT EXISTS ix_report_chunks_finding_id ON report_chunks(finding_id);
CREATE INDEX IF NOT EXISTS ix_report_chunks_embedding ON report_chunks USING hnsw (embedding vector_cosine_ops);
"""


def banner(text: str) -> None:
    line = "=" * 72
    print(f"\n{line}\n  {text}\n{line}", flush=True)


async def check_and_migrate_db() -> bool:
    """Check PostgreSQL connection and apply vector extension and table DDL."""
    try:
        import asyncpg
    except ImportError:
        logger.warning("asyncpg is not installed. Skipping direct PostgreSQL check.")
        return False

    try:
        conn = await asyncpg.connect(DB_URL, timeout=5.0)
    except Exception as e:
        logger.warning(f"Could not connect to PostgreSQL at {DB_URL} ({e}).")
        logger.warning("RAG will run using local catalog (var/catalog.sqlite3).")
        return False

    try:
        logger.info("Connected to PostgreSQL. Verifying 'report_chunks' table and HNSW index...")
        await conn.execute(TABLE_DDL)
        logger.info("[ OK ] PostgreSQL pgvector schema verified (report_chunks table ready).")
        return True
    finally:
        await conn.close()


def build_chunks(report_id: uuid.UUID, data: Dict[str, Any], observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Slice report JSON & observations into chunks."""
    chunks = []
    chunk_idx = 0

    # Executive Summary
    exec_summary = data.get("executive_summary")
    if isinstance(exec_summary, dict):
        narrative = exec_summary.get("narrative") or exec_summary.get("summary")
        if narrative and str(narrative).strip():
            chunks.append({
                "section_id": "executive_summary",
                "finding_id": None,
                "context_prefix": "Executive Summary",
                "chunk": str(narrative).strip(),
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    # Scope & Methodology
    scope = data.get("scope") or data.get("engagement_scope")
    if isinstance(scope, dict):
        desc = scope.get("description") or scope.get("assets")
        if desc:
            chunks.append({
                "section_id": "scope",
                "finding_id": None,
                "context_prefix": "Engagement Scope",
                "chunk": f"Scope: {desc}",
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    # Observations / Findings
    findings = observations or data.get("detailed_observations") or data.get("vulnerabilities") or []
    for obs in findings:
        if not isinstance(obs, dict):
            continue
        fid = str(obs.get("finding_id") or obs.get("id") or "").strip()
        title = str(obs.get("title") or obs.get("vulnerability_title") or "").strip()
        desc = str(
            obs.get("observation_description")
            or obs.get("detailed_observation")
            or obs.get("observation")
            or obs.get("description")
            or ""
        ).strip()
        recom = str(obs.get("recommendation") or obs.get("remediation") or "").strip()
        impact = str(obs.get("impact") or obs.get("business_impact") or "").strip()
        sev = str(obs.get("severity") or obs.get("risk_rating") or "").strip()

        header = f"Finding {fid}: {title} ({sev})" if sev else f"Finding {fid}: {title}"
        parts = []
        if desc: parts.append(f"Observation: {desc}")
        if impact: parts.append(f"Impact: {impact}")
        if recom: parts.append(f"Recommendation: {recom}")

        if parts:
            chunks.append({
                "section_id": f"finding_{fid}" if fid else "findings",
                "finding_id": fid or None,
                "context_prefix": header,
                "chunk": "\n".join(parts),
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    return chunks


async def sync_catalog_sqlite(pool) -> None:
    """Index Postgres reports into the chat engine through its normal ingest.

    Reports go through the same pipeline as any other source: validation,
    CWE/CVE tables and search in var/catalog.sqlite3, vectors in the rag schema.
    Reports already exported are left alone, and unchanged files are
    skipped by the ingest, so a restart only embeds what is new.
    """
    from ragaudit.config import load_settings
    from ragaudit.corpus_tools import postgres_report_document

    sync_dir = load_settings().data_dir / "pg_sync"
    sync_dir.mkdir(parents=True, exist_ok=True)

    async with pool.acquire() as conn:
        reports_rows = await conn.fetch("""
            SELECT r.report_id, r.original_filename, rd.data
            FROM reports r
            JOIN reports_data rd ON r.report_id = rd.report_id
        """)
        obs_rows = await conn.fetch("""
            SELECT report_id, finding_id, title, severity, status, cvss_score, cvss_vector, cwe, cve_id,
                   affected_asset, observation_description, impact, likely_root_cause, recommendation,
                   reference, regulatory_references, severity_rationale, observation_date
            FROM detailed_observations
        """)

    observations: Dict[str, List[Dict[str, Any]]] = {}
    for o in obs_rows:
        row = {k: v for k, v in dict(o).items() if k != "report_id" and v is not None}
        observations.setdefault(str(o["report_id"]), []).append(row)

    exported = 0
    for r in reports_rows:
        rid = str(r["report_id"])
        target = sync_dir / f"{rid}.json"
        if target.exists():
            continue
        raw = r["data"]
        data = json.loads(raw) if isinstance(raw, str) else raw
        doc = postgres_report_document(data or {}, observations.get(rid, []), rid, r["original_filename"] or "")
        target.write_text(json.dumps(doc, default=str), encoding="utf-8")
        exported += 1

    logger.info(f"Exported {exported} new report(s) of {len(reports_rows)}. Running ingest...")
    # A child process, so the embedding model's memory is freed before the server loads its own.
    code = subprocess.call([sys.executable, "-m", "ragaudit.cli", "ingest", str(sync_dir)], cwd=str(ENGINE_DIR))
    if code:
        logger.warning(f"Ingest exited with code {code}; see its output above. Serving what was indexed.")
    else:
        logger.info("[ OK ] Web console catalogue and vector index are in sync with PostgreSQL.")


async def sync_past_reports(force: bool = False) -> None:
    """Backfill past reports from PostgreSQL into report_chunks and SQLite catalogue."""
    import asyncpg
    from ragaudit.config import load_settings
    from ragaudit.retrieve.embedder import Embedder

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=5, timeout=10.0)
    try:
        async with pool.acquire() as conn:
            total_reports = await conn.fetchval("SELECT count(*) FROM reports_data;")
            existing_chunks = await conn.fetchval("SELECT count(*) FROM report_chunks;")
            indexed_reports = await conn.fetchval("SELECT count(DISTINCT report_id) FROM report_chunks;")

        logger.info(f"PostgreSQL Status: {total_reports} reports in DB, {indexed_reports} indexed ({existing_chunks} chunks).")

        if not force and indexed_reports >= total_reports and existing_chunks > 0:
            logger.info(f"[ OK ] All {total_reports} reports are already synchronized in pgvector ({existing_chunks} chunks ready).")
            await sync_catalog_sqlite(pool)
            return

        async with pool.acquire() as conn:
            if force:
                rows = await conn.fetch("SELECT rd.report_id, rd.data, r.original_filename FROM reports_data rd JOIN reports r ON rd.report_id = r.report_id ORDER BY r.created_at ASC;")
            else:
                rows = await conn.fetch("""
                    SELECT rd.report_id, rd.data, r.original_filename 
                    FROM reports_data rd 
                    JOIN reports r ON rd.report_id = r.report_id 
                    WHERE rd.report_id NOT IN (SELECT DISTINCT report_id FROM report_chunks)
                    ORDER BY r.created_at ASC;
                """)

        if not rows:
            logger.info("[ OK ] No new reports to backfill.")
            await sync_catalog_sqlite(pool)
            return

        logger.info(f"Backfilling {len(rows)} report(s) into pgvector and RAG catalogue...")

        # Load embedding model
        cfg = load_settings()
        model_path = Path(cfg.embedding.model_path)
        if not model_path.is_absolute():
            model_path = ENGINE_DIR / model_path

        embedder = Embedder(str(model_path), device=cfg.embedding.device, batch_size=cfg.embedding.batch_size)
        logger.info(f"Loading embedding model from {model_path}...")
        embedder.load()

        total_inserted = 0
        insert_sql = """
            INSERT INTO report_chunks (
                chunk_id, report_id, section_id, chunk, embedding, 
                chunk_index, context_prefix, finding_id, token_count, meta
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """

        for i, row in enumerate(rows, start=1):
            rep_id = row["report_id"]
            filename = row["original_filename"]
            raw_data = row["data"]
            data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data

            obs_rows = []
            for attempt in range(3):
                try:
                    async with pool.acquire() as conn:
                        obs_rows = await conn.fetch(
                            """SELECT finding_id, title, severity, status, observation_description, 
                                      recommendation, impact, affected_asset, cwe, cve_id, cvss_score 
                               FROM detailed_observations WHERE report_id = $1""",
                            rep_id
                        )
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.warning(f"Could not fetch observations for {rep_id}: {e}")
                    await asyncio.sleep(0.5)

            observations = [dict(r) for r in obs_rows]
            chunks = build_chunks(rep_id, data, observations)
            if not chunks:
                continue

            texts = [c["chunk"] for c in chunks]
            vectors = embedder.embed_passages(texts)

            for attempt in range(3):
                try:
                    async with pool.acquire() as conn:
                        async with conn.transaction():
                            await conn.execute("DELETE FROM report_chunks WHERE report_id = $1;", rep_id)
                            for chunk_data, vec in zip(chunks, vectors):
                                cid = uuid.uuid4()
                                vec_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                                await conn.execute(
                                    insert_sql,
                                    cid,
                                    rep_id,
                                    chunk_data["section_id"],
                                    chunk_data["chunk"],
                                    vec_str,
                                    chunk_data["chunk_index"],
                                    chunk_data["context_prefix"],
                                    chunk_data["finding_id"],
                                    len(chunk_data["chunk"].split()),
                                    json.dumps({"filename": filename}),
                                )
                                total_inserted += 1
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.error(f"Failed to insert report {rep_id} after 3 attempts: {e}")
                    await asyncio.sleep(0.5)

            if i % 10 == 0 or i == len(rows):
                logger.info(f"  Progress: [{i}/{len(rows)}] reports processed ({total_inserted} new chunks stored)")

        logger.info(f"[ OK ] Backfill complete: {total_inserted} chunks stored in PostgreSQL report_chunks table.")
        await sync_catalog_sqlite(pool)

    finally:
        await pool.close()


def ensure_ollama() -> None:
    """Ensure Ollama is running and accessible."""
    ollama_host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        with urllib.request.urlopen(f"{ollama_host}/api/tags", timeout=3) as resp:
            models = [m.get("name") for m in json.load(resp).get("models", [])]
            logger.info(f"[ OK ] Ollama is online with {len(models)} model(s).")
    except Exception:
        logger.warning(f"Ollama is not reachable at {ollama_host}.")
        logger.warning("Make sure Ollama is running ('ollama serve' and 'ollama pull qwen3:8b').")


def start_server(host: str = "0.0.0.0", port: int = 8077) -> None:
    """Start uvicorn server serving the RAG Web Console and API."""
    import uvicorn
    banner(
        f"RAG Web Console Ready!\n"
        f"  Open in Browser:  http://localhost:{port}\n"
        f"  API Docs:         http://localhost:{port}/docs\n"
        f"  (Note: Windows does not resolve 0.0.0.0 in browsers. Always use localhost:{port})"
    )
    uvicorn.run("ragaudit.api.server:app", host=host, port=port, log_level="info")


def main() -> None:
    parser = argparse.ArgumentParser(description="Single master launcher for RAG engine, migrations, and sync.")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8077, help="Port to bind (default 8077)")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip historical PostgreSQL ingest check")
    parser.add_argument("--force", action="store_true", help="Force re-indexing all past reports")

    args = parser.parse_args()

    banner("Step 1/3: Checking PostgreSQL & Running pgvector Migrations")
    db_ok = asyncio.run(check_and_migrate_db())

    if db_ok:
        os.environ["RAGAUDIT_RETRIEVAL__BACKEND"] = "pgvector"
        os.environ["RAGAUDIT_RETRIEVAL__PG_DSN"] = DB_URL

    if db_ok and not args.skip_ingest:
        banner("Step 2/3: Checking & Synchronizing Historical Reports")
        try:
            asyncio.run(sync_past_reports(force=args.force))
        except Exception as e:
            logger.error(f"Error during historical report sync: {e}", exc_info=True)
    else:
        logger.info("Skipping historical sync (skip-ingest flag or DB unreachable).")

    banner("Step 3/3: Checking Local LLM & Starting RAG Service")
    ensure_ollama()
    start_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
