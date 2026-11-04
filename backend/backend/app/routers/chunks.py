import uuid
import logging
from typing import List, Optional
from datetime import datetime, timezone
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, text

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.report import Report, ReportsData, ReportChunk
from app.schemas.chunk import (
    ChunkCreate,
    ChunkBatchCreate,
    ChunkOut,
    ChunkSearchRequest,
    ChunkSearchResult,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["RAG & Chunks"])


@router.post("/reports/{report_id}/chunks", response_model=List[ChunkOut], status_code=status.HTTP_201_CREATED)
async def create_report_chunks(
    report_id: uuid.UUID,
    payload: ChunkBatchCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Store a batch of text chunks and their pgvector embeddings for a specific report.
    """
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    created: List[ReportChunk] = []
    for item in payload.chunks:
        chunk_obj = ReportChunk(
            report_id=report_id,
            section_id=item.section_id,
            chunk=item.chunk,
            embedding=item.embedding,
            chunk_index=item.chunk_index,
            context_prefix=item.context_prefix,
            finding_id=item.finding_id,
            token_count=item.token_count,
            meta_data=item.meta_data,
        )
        db.add(chunk_obj)
        created.append(chunk_obj)

    await db.commit()
    for obj in created:
        await db.refresh(obj)

    return [
        ChunkOut(
            chunk_id=c.chunk_id,
            report_id=c.report_id,
            section_id=c.section_id,
            chunk=c.chunk,
            finding_id=c.finding_id,
            context_prefix=c.context_prefix,
            chunk_index=c.chunk_index,
            token_count=c.token_count,
            meta_data=c.meta_data,
            created_at=c.created_at,
            updated_at=c.updated_at,
            has_embedding=c.embedding is not None,
        )
        for c in created
    ]


@router.get("/reports/{report_id}/chunks", response_model=List[ChunkOut])
async def get_report_chunks(
    report_id: uuid.UUID,
    section_id: Optional[str] = Query(None, description="Filter by section ID"),
    finding_id: Optional[str] = Query(None, description="Filter by finding ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve stored chunks for a given report, with optional section or finding filters.
    """
    query = select(ReportChunk).where(ReportChunk.report_id == report_id)
    if section_id:
        query = query.where(ReportChunk.section_id == section_id)
    if finding_id:
        query = query.where(ReportChunk.finding_id == finding_id)

    query = query.order_by(ReportChunk.chunk_index.asc().nulls_last(), ReportChunk.created_at.asc()).offset(offset).limit(limit)
    res = await db.execute(query)
    chunks = res.scalars().all()

    return [
        ChunkOut(
            chunk_id=c.chunk_id,
            report_id=c.report_id,
            section_id=c.section_id,
            chunk=c.chunk,
            finding_id=c.finding_id,
            context_prefix=c.context_prefix,
            chunk_index=c.chunk_index,
            token_count=c.token_count,
            meta_data=c.meta_data,
            created_at=c.created_at,
            updated_at=c.updated_at,
            has_embedding=c.embedding is not None,
        )
        for c in chunks
    ]


@router.delete("/reports/{report_id}/chunks", status_code=status.HTTP_200_OK)
async def delete_report_chunks(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all chunks for a report."""
    await db.execute(delete(ReportChunk).where(ReportChunk.report_id == report_id))
    await db.commit()
    return {"message": f"Chunks for report {report_id} deleted"}


@router.post("/reports/{report_id}/chunk-and-index", status_code=status.HTTP_200_OK)
async def chunk_and_index_report(
    report_id: uuid.UUID,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Automatically partition the standardized report JSON (from ReportsData)
    into sections and findings chunks, compute embeddings via RAG service if available,
    and persist into pgvector table report_chunks.
    """
    rd_res = await db.execute(select(ReportsData).where(ReportsData.report_id == report_id))
    rd = rd_res.scalar_one_or_none()
    if not rd or not rd.data:
        raise HTTPException(
            status_code=400,
            detail="No standardized pipeline JSON found for this report. Run the standardization pipeline first.",
        )

    data = rd.data
    chunks_to_create: List[dict] = []
    chunk_idx = 0

    # 1. Executive Summary & Narrative
    exec_summary = data.get("executive_summary")
    if isinstance(exec_summary, dict):
        narrative = exec_summary.get("narrative")
        if narrative and str(narrative).strip():
            chunks_to_create.append({
                "section_id": "executive_summary",
                "finding_id": None,
                "context_prefix": "Executive Summary",
                "chunk": str(narrative).strip(),
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    # 2. Methodology & Scope
    methodology = data.get("methodology")
    if isinstance(methodology, dict):
        standards = methodology.get("standards_referred", [])
        if standards:
            chunks_to_create.append({
                "section_id": "methodology",
                "finding_id": None,
                "context_prefix": "Methodology > Standards",
                "chunk": f"Standards referred: {', '.join(str(s) for s in standards)}",
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    # 3. Detailed observations / findings
    observations = data.get("detailed_observations") or data.get("vulnerabilities") or []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        fid = str(obs.get("finding_id") or obs.get("id") or "").strip()
        title = str(obs.get("title") or obs.get("vulnerability_title") or "").strip()
        desc = str(obs.get("observation_description") or obs.get("detailed_observation") or obs.get("observation") or "").strip()
        recom = str(obs.get("recommendation") or obs.get("remediation") or "").strip()
        impact = str(obs.get("impact") or obs.get("business_impact") or "").strip()

        finding_header = f"Finding {fid}: {title}" if fid else title
        parts = []
        if desc:
            parts.append(f"Observation: {desc}")
        if impact:
            parts.append(f"Impact: {impact}")
        if recom:
            parts.append(f"Recommendation: {recom}")

        if parts:
            full_text = "\n".join(parts)
            chunks_to_create.append({
                "section_id": f"finding_{fid}" if fid else "findings",
                "finding_id": fid or None,
                "context_prefix": finding_header,
                "chunk": full_text,
                "chunk_index": chunk_idx,
            })
            chunk_idx += 1

    # Request embeddings from RAG Service if available
    texts = [c["chunk"] for c in chunks_to_create]
    embeddings: List[Optional[List[float]]] = [None] * len(texts)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.RAG_SERVICE_URL}/api/embed",
                json={"texts": texts},
            )
            if resp.status_code == 200:
                payload = resp.json()
                embeddings = payload.get("embeddings", embeddings)
    except Exception as e:
        logger.warning(f"RAG service embed request could not be completed ({e}); chunks stored without initial embedding.")

    # Remove old chunks for this report to maintain idempotency
    await db.execute(delete(ReportChunk).where(ReportChunk.report_id == report_id))

    for item, emb in zip(chunks_to_create, embeddings):
        chunk_obj = ReportChunk(
            report_id=report_id,
            section_id=item["section_id"],
            chunk=item["chunk"],
            embedding=emb,
            chunk_index=item["chunk_index"],
            context_prefix=item["context_prefix"],
            finding_id=item["finding_id"],
            token_count=len(item["chunk"].split()),
        )
        db.add(chunk_obj)

    await db.commit()

    return {
        "report_id": report_id,
        "chunks_indexed": len(chunks_to_create),
        "embedded": sum(1 for e in embeddings if e is not None),
    }


@router.post("/chunks/search", response_model=List[ChunkSearchResult])
async def search_chunks_pgvector(
    req: ChunkSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search chunks across reports using pgvector cosine distance similarity.
    Accepts either a pre-computed query vector (1024-dim) or text query
    (which gets embedded on the fly via the RAG service).
    """
    query_vector = req.query_vector

    # If text is supplied without vector, request embedding from RAG service
    if not query_vector and req.query_text:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{settings.RAG_SERVICE_URL}/api/embed",
                    json={"texts": [req.query_text]},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    embs = data.get("embeddings", [])
                    if embs:
                        query_vector = embs[0]
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Could not reach RAG service to embed query text: {e}",
            )

    if not query_vector:
        raise HTTPException(
            status_code=400,
            detail="Either query_vector or query_text must be provided for similarity search",
        )

    # Format vector as string for pgvector '[0.1, 0.2, ...]'
    vec_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"

    filters = ["embedding IS NOT NULL"]
    params: dict = {"vec": vec_str, "top_k": req.top_k}

    if req.report_id:
        filters.append("report_id = :report_id")
        params["report_id"] = str(req.report_id)
    if req.section_id:
        filters.append("section_id = :section_id")
        params["section_id"] = req.section_id

    filter_clause = " AND ".join(filters)

    # pgvector cosine distance operator <=>
    sql = text(f"""
        SELECT 
            chunk_id, 
            report_id, 
            section_id, 
            chunk, 
            finding_id, 
            context_prefix,
            (embedding <=> (:vec)::vector) AS distance
        FROM report_chunks
        WHERE {filter_clause}
        ORDER BY distance ASC
        LIMIT :top_k
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    out = []
    for r in rows:
        dist = float(r.distance) if r.distance is not None else 1.0
        # Cosine distance ranges from 0 (identical) to 2 (opposite); cosine similarity = 1 - distance
        score = max(0.0, 1.0 - dist)
        out.append(
            ChunkSearchResult(
                chunk_id=r.chunk_id,
                report_id=r.report_id,
                section_id=r.section_id,
                chunk=r.chunk,
                finding_id=r.finding_id,
                context_prefix=r.context_prefix,
                distance=dist,
                score=score,
            )
        )

    return out

