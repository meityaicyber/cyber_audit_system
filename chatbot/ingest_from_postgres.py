#!/usr/bin/env python3
"""Ingest cybersecurity audit reports directly from PostgreSQL into RAG and PGVector.

Usage:
    python ingest_from_postgres.py                     # Ingest all available reports from PostgreSQL
    python ingest_from_postgres.py --limit 5           # Ingest first 5 reports
    python ingest_from_postgres.py --report-id <UUID>  # Ingest a specific report
    python ingest_from_postgres.py --verify            # Verify chunk counts & vector search in PostgreSQL
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from dotenv import load_dotenv

# Ensure ragaudit is on PYTHONPATH
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ragaudit.config import load_settings
from ragaudit.retrieve.embedder import Embedder

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ingest_from_postgres")

# Read DATABASE_URL or fallback to local docker defaults
load_dotenv(ROOT / ".env")
DEFAULT_DB_URL = os.environ.get(
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


async def ensure_schema(conn: asyncpg.Connection) -> None:
    """Ensure pgvector extension and report_chunks table exist."""
    await conn.execute(TABLE_DDL)


def build_chunks_from_report(db_report_id: uuid.UUID, data: Dict[str, Any], observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Partition a report's JSON and observations into section-level and finding-level chunks."""
    chunks = []
    chunk_idx = 0

    # 1. Executive Summary
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

    # 2. Scope & Methodology
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

    methodology = data.get("methodology")
    if isinstance(methodology, dict):
        standards = methodology.get("standards_referred", [])
        if standards:
            chunks.append({
                "section_id": "methodology",
                "finding_id": None,
                "context_prefix": "Methodology",
                "chunk": f"Standards referred: {', '.join(str(s) for s in standards)}",
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    # 3. Observations / Findings (from detailed_observations table or JSON)
    findings_sources = observations or data.get("detailed_observations") or data.get("vulnerabilities") or []
    for obs in findings_sources:
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

        finding_header = f"Finding {fid}: {title} ({sev})" if sev else f"Finding {fid}: {title}"
        parts = []
        if desc:
            parts.append(f"Observation: {desc}")
        if impact:
            parts.append(f"Impact: {impact}")
        if recom:
            parts.append(f"Recommendation: {recom}")

        if parts:
            full_text = "\n".join(parts)
            chunks.append({
                "section_id": f"finding_{fid}" if fid else "findings",
                "finding_id": fid or None,
                "context_prefix": finding_header,
                "chunk": full_text,
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    return chunks


async def run_ingest(
    db_url: str,
    *,
    limit: Optional[int] = None,
    target_report_id: Optional[uuid.UUID] = None,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    logger.info(f"Connecting to PostgreSQL at {db_url}...")
    conn = await asyncpg.connect(db_url)
    try:
        await ensure_schema(conn)

        # 1. Fetch reports from reports_data
        if target_report_id:
            query = """
                SELECT rd.report_id, rd.data, r.original_filename 
                FROM reports_data rd
                JOIN reports r ON rd.report_id = r.report_id
                WHERE rd.report_id = $1
            """
            rows = await conn.fetch(query, target_report_id)
        else:
            query = """
                SELECT rd.report_id, rd.data, r.original_filename 
                FROM reports_data rd
                JOIN reports r ON rd.report_id = r.report_id
                ORDER BY r.created_at DESC
            """
            if limit:
                query += f" LIMIT {int(limit)}"
            rows = await conn.fetch(query)

        logger.info(f"Found {len(rows)} report(s) in PostgreSQL to ingest.")
        if not rows:
            return

        # 2. Setup Embedder
        settings = load_settings()
        model_path = Path(settings.embedding.model_path)
        if not model_path.is_absolute():
            model_path = ROOT / model_path

        embedder = Embedder(
            str(model_path),
            device=settings.embedding.device,
            batch_size=settings.embedding.batch_size,
        )
        logger.info(f"Loading embedding model from {settings.embedding.model_path}...")
        embedder.load()
        logger.info(f"Embedding model ready (dimension: {embedder.dimension}).")

        # 3. Process each report
        total_chunks = 0
        for i, row in enumerate(rows, start=1):
            report_id = row["report_id"]
            filename = row["original_filename"]
            raw_data = row["data"]
            data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data

            # Fetch detailed observations from DB table if available
            obs_rows = await conn.fetch(
                """SELECT finding_id, title, severity, status, observation_description, 
                          recommendation, impact, affected_asset, cwe, cve_id, cvss_score 
                   FROM detailed_observations WHERE report_id = $1""",
                report_id
            )
            observations = [dict(r) for r in obs_rows]

            # Reconstruct chunks
            chunks = build_chunks_from_report(report_id, data, observations)
            logger.info(
                f"[{i}/{len(rows)}] Report {report_id} ({filename}): "
                f"built {len(chunks)} chunks ({len(observations)} observations in DB)"
            )

            if dry_run or not chunks:
                continue

            # Compute embeddings in batch
            texts = [c["chunk"] for c in chunks]
            vectors = embedder.embed_passages(texts)

            # Insert into report_chunks table in PostgreSQL
            # Remove old chunks for this report if re-ingesting
            await conn.execute("DELETE FROM report_chunks WHERE report_id = $1;", report_id)

            insert_sql = """
                INSERT INTO report_chunks (
                    chunk_id, report_id, section_id, chunk, embedding, 
                    chunk_index, context_prefix, finding_id, token_count, meta
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """

            for chunk_data, vec in zip(chunks, vectors):
                chunk_id = uuid.uuid4()
                # Format embedding as string '[0.1, 0.2, ...]' for pgvector
                vec_str = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                await conn.execute(
                    insert_sql,
                    chunk_id,
                    report_id,
                    chunk_data["section_id"],
                    chunk_data["chunk"],
                    vec_str,
                    chunk_data["chunk_index"],
                    chunk_data["context_prefix"],
                    chunk_data["finding_id"],
                    len(chunk_data["chunk"].split()),
                    json.dumps({"pipeline_file": filename}),
                )
                total_chunks += 1

        logger.info(f"Ingestion complete: {total_chunks} chunks stored into PostgreSQL report_chunks with pgvector embeddings.")

    finally:
        await conn.close()


async def verify_postgres_chunks(db_url: str) -> None:
    """Run verification queries against the report_chunks table in PostgreSQL."""
    conn = await asyncpg.connect(db_url)
    try:
        count = await conn.fetchval("SELECT count(*) FROM report_chunks;")
        reports_count = await conn.fetchval("SELECT count(DISTINCT report_id) FROM report_chunks;")
        logger.info("=================================================================")
        logger.info("  POSTGRESQL PGVECTOR VERIFICATION")
        logger.info("=================================================================")
        logger.info(f"  Total rows in 'report_chunks' table : {count}")
        logger.info(f"  Unique reports indexed              : {reports_count}")

        if count > 0:
            sample = await conn.fetchrow(
                "SELECT chunk_id, report_id, section_id, context_prefix, chunk, (embedding IS NOT NULL) as has_vector FROM report_chunks LIMIT 1;"
            )
            logger.info(f"  Sample Chunk ID : {sample['chunk_id']}")
            logger.info(f"  Section ID      : {sample['section_id']}")
            logger.info(f"  Context Prefix  : {sample['context_prefix']}")
            logger.info(f"  Has Vector?     : {sample['has_vector']}")
            logger.info(f"  Chunk Preview   : {sample['chunk'][:120]}...")

            # Run a pgvector cosine similarity test
            logger.info("  Running vector similarity search test (<=> operator)...")
            similar = await conn.fetch(
                """
                SELECT chunk_id, section_id, context_prefix, (embedding <=> (SELECT embedding FROM report_chunks WHERE embedding IS NOT NULL LIMIT 1)) AS distance
                FROM report_chunks
                WHERE embedding IS NOT NULL
                ORDER BY distance ASC
                LIMIT 3;
                """
            )
            for r in similar:
                dist = float(r['distance'])
                logger.info(f"    - Chunk {r['chunk_id']} [{r['section_id']}] -> distance: {dist:.4f} (score: {max(0.0, 1.0 - dist):.4f})")

        logger.info("=================================================================")
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest reports from PostgreSQL into pgvector and RAG.")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL, help="PostgreSQL connection string")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of reports to ingest")
    parser.add_argument("--report-id", type=str, default=None, help="Target specific report UUID")
    parser.add_argument("--all", action="store_true", help="Ingest all available reports")
    parser.add_argument("--dry-run", action="store_true", help="Preview chunks without writing")
    parser.add_argument("--force", action="store_true", help="Force re-indexing")
    parser.add_argument("--verify", action="store_true", help="Verify table and vector search in PostgreSQL")

    args = parser.parse_args()

    target_uuid = uuid.UUID(args.report_id) if args.report_id else None

    if args.verify:
        asyncio.run(verify_postgres_chunks(args.db_url))
        return

    # Default to 5 reports if not specified, or all if --all is passed
    limit = None if args.all else (args.limit or 5)
    asyncio.run(
        run_ingest(
            args.db_url,
            limit=limit,
            target_report_id=target_uuid,
            force=args.force,
            dry_run=args.dry_run,
        )
    )
    asyncio.run(verify_postgres_chunks(args.db_url))


if __name__ == "__main__":
    main()
