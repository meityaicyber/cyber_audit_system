"""
RAG Ingest Worker Service
-------------------------
Multi-threaded worker pool that processes standardized report JSONs asynchronously
when returned by the AI pipeline:
1. Persists ReportsData and DetailedObservation in PostgreSQL.
2. Extracts sections/findings into report_chunks with pgvector embeddings.
3. Dispatches an API call to the RAG service (/api/ingest-json) to index the
   document into the air-gapped RAG catalogue and vector store under the exact
   report_id returned by the pipeline.
"""

import asyncio
import copy
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import httpx
from sqlalchemy.future import select
from sqlalchemy import delete

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.report import (
    ReportsData,
    DetailedObservation,
    ObservationSeverity,
    ObservationStatus,
    ObservationImpact,
    ObservationLikelihood,
    ObservationNewRepeat,
)

logger = logging.getLogger(__name__)

# Multi-threaded background worker pool
RAG_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag-worker")


def _run_async(coro):
    """Helper to run an async coroutine synchronously inside a background worker thread."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _save_observations_and_data(db_report_id: uuid.UUID, report_data: Dict[str, Any]):
    """Persist ReportsData and DetailedObservation records."""
    data_copy = copy.deepcopy(report_data)
    vulns = data_copy.pop("detailed_observations", data_copy.pop("vulnerabilities", []))

    async with AsyncSessionLocal() as session:
        existing_rd_res = await session.execute(
            select(ReportsData).where(ReportsData.report_id == db_report_id)
        )
        rd = existing_rd_res.scalar_one_or_none()
        if rd:
            rd.data = data_copy
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(rd, "data")
            rd.updated_at = datetime.now(timezone.utc)
        else:
            rd = ReportsData(report_id=db_report_id, data=data_copy)
            session.add(rd)

        await session.execute(
            delete(DetailedObservation).where(DetailedObservation.report_id == db_report_id)
        )

        for v in vulns:
            if not isinstance(v, dict):
                continue
            severity_str = str(v.get("severity", "")).upper()
            severity_enum = None
            if severity_str == "CRITICAL": severity_enum = ObservationSeverity.CRITICAL
            elif severity_str == "HIGH": severity_enum = ObservationSeverity.HIGH
            elif severity_str == "MEDIUM": severity_enum = ObservationSeverity.MEDIUM
            elif severity_str == "LOW": severity_enum = ObservationSeverity.LOW

            status_str = str(v.get("status", "")).upper()
            status_enum = None
            if status_str == "OPEN": status_enum = ObservationStatus.OPEN
            elif status_str == "CLOSED": status_enum = ObservationStatus.CLOSED
            elif "PARTIALLY" in status_str: status_enum = ObservationStatus.PARTIALLY_REMEDIATED

            impact_str = str(v.get("impact_level", "")).upper()
            impact_enum = None
            if impact_str == "MAJOR": impact_enum = ObservationImpact.MAJOR
            elif impact_str == "MODERATE": impact_enum = ObservationImpact.MODERATE
            elif impact_str == "MINOR": impact_enum = ObservationImpact.MINOR

            like_str = str(v.get("likelihood_level", "")).upper()
            like_enum = None
            if like_str == "EASY": like_enum = ObservationLikelihood.EASY
            elif like_str == "MODERATE": like_enum = ObservationLikelihood.MODERATE
            elif like_str == "HARD": like_enum = ObservationLikelihood.HARD

            nr_str = str(v.get("new_or_repeat", "")).upper()
            nr_enum = None
            if nr_str == "NEW": nr_enum = ObservationNewRepeat.NEW
            elif nr_str == "REPEAT": nr_enum = ObservationNewRepeat.REPEAT

            obs_date = None
            date_str = v.get("observation_date")
            if date_str:
                try:
                    obs_date = datetime.strptime(str(date_str).strip(), "%Y-%m-%d").date()
                except ValueError:
                    pass

            obs = DetailedObservation(
                report_id=db_report_id,
                title=v.get("title", v.get("vulnerability_title", "Unknown Title")),
                status=status_enum,
                severity=severity_enum,
                impact_level=impact_enum,
                likelihood_level=like_enum,
                cve_id=v.get("cve_id", v.get("cve_ids", [])),
                cvss_score=v.get("cvss_score"),
                cvss_vector=v.get("cvss_vector"),
                severity_rationale=v.get("severity_rationale"),
                reported_epss_score=v.get("reported_epss_score"),
                observation_date=obs_date,
                cwe=v.get("cwe", v.get("cwe_ids", [])),
                affected_asset=v.get("affected_asset", v.get("affected_assets", [])),
                regulatory_references=v.get("regulatory_references", []),
                observation_description=v.get("observation_description", v.get("detailed_observation")),
                preconditions=v.get("preconditions"),
                proof_of_concept=v.get("proof_of_concept"),
                impact=v.get("impact"),
                likely_root_cause=v.get("likely_root_cause"),
                recommendation=v.get("recommendation"),
                reference=v.get("reference"),
                new_or_repeat=nr_enum,
                meta_data=v.get("additional meta", {}),
            )
            session.add(obs)

        await session.commit()
    logger.info(f"[RAG-Worker] Stored report {db_report_id} and {len(vulns)} observations in PostgreSQL")


async def _save_pgvector_chunks(db_report_id: uuid.UUID):
    """Chunk and index the report in PostgreSQL report_chunks using pgvector."""
    from app.routers.chunks import chunk_and_index_report
    async with AsyncSessionLocal() as session:
        result = await chunk_and_index_report(db_report_id, current_user=None, db=session)
        logger.info(f"[RAG-Worker] PGVector chunking result for report {db_report_id}: {result}")


def _call_rag_ingest_api(pipeline_report_id: str, report_data: Dict[str, Any]):
    """Call the RAG service API to run the ingest pipeline."""
    rag_url = f"{settings.RAG_SERVICE_URL}/api/ingest-json"
    payload = {
        "report_id": pipeline_report_id,
        "data": report_data,
    }
    logger.info(f"[RAG-Worker] Calling RAG ingest API at {rag_url} for report '{pipeline_report_id}'...")
    try:
        with httpx.Client(timeout=300.0) as client:
            resp = client.post(rag_url, json=payload)
            if resp.status_code == 200:
                logger.info(f"[RAG-Worker] Successfully indexed report '{pipeline_report_id}' in RAG Engine: {resp.json()}")
            else:
                logger.error(f"[RAG-Worker] RAG service returned status {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.warning(f"[RAG-Worker] Could not reach RAG service at {rag_url} ({e}). Local pgvector chunks are still preserved.")


def process_and_index_report_job(
    db_report_id: uuid.UUID,
    pipeline_report_id: str,
    report_data: Dict[str, Any],
):
    """
    Worker function executed inside the ThreadPoolExecutor.
    Runs DB saves, pgvector chunk extraction, and calls the RAG ingest API.
    """
    logger.info(f"[RAG-Worker] Starting processing job for report {db_report_id} (pipeline report_id: '{pipeline_report_id}')")
    try:
        # Step 1: Save standard DB records (ReportsData, DetailedObservation)
        _run_async(_save_observations_and_data(db_report_id, report_data))

        # Step 2: Auto-partition and store pgvector chunks
        try:
            _run_async(_save_pgvector_chunks(db_report_id))
        except Exception as chunk_err:
            logger.warning(f"[RAG-Worker] Error creating pgvector chunks for {db_report_id}: {chunk_err}")

        # Step 3: Call RAG ingest pipeline via API with pipeline_report_id
        _call_rag_ingest_api(pipeline_report_id, report_data)

        logger.info(f"[RAG-Worker] Completed processing and indexing job for report {db_report_id} ('{pipeline_report_id}')")
    except Exception as exc:
        logger.error(f"[RAG-Worker] Unhandled error processing report {db_report_id}: {exc}", exc_info=True)


def dispatch_rag_ingest_job(
    db_report_id: uuid.UUID,
    pipeline_report_id: str,
    report_data: Dict[str, Any],
) -> Future:
    """
    Submit a report indexing job to the multi-threaded worker pool.
    Returns immediately without blocking the request/stream.
    """
    logger.info(f"[RAG-Worker] Queued indexing job for report {db_report_id} (pipeline_id='{pipeline_report_id}')")
    return RAG_EXECUTOR.submit(
        process_and_index_report_job,
        db_report_id,
        pipeline_report_id,
        report_data,
    )

