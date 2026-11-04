"""
Pipeline Router
---------------
Proxy endpoint that downloads a report from storage,
forwards it to the AI Pipeline service, and returns the results.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from datetime import datetime, timezone
import httpx

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.report import ReportsData, DetailedObservation, ObservationSeverity, ObservationStatus, ObservationImpact, ObservationLikelihood, ObservationNewRepeat
from app.services import report_service
from app.config import settings

router = APIRouter(prefix="/api/reports", tags=["Pipeline"])


@router.post("/{report_id}/run-pipeline")
async def run_pipeline(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run the AI pipeline on a report.
    Downloads the report file from SeaweedFS, forwards it to the
    AI Pipeline microservice, and returns the analysis results.
    """
    from app.utils.seaweedfs_utils import get_file_bytes

    # 1. Fetch the report record
    report = await report_service.get_report_by_id(db, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    if not report.storage or not report.storage.encrypted_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File storage record not found",
        )

    # 2. Download file from SeaweedFS
    object_name = report.storage.encrypted_file_path
    try:
        encrypted_data = get_file_bytes(object_name)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found in storage: {e}",
        )

    # 3. Decrypt if needed
    if report.storage.encryption_algorithm == "Fernet":
        from app.utils.encryption_utils import decrypt_file
        file_data = decrypt_file(encrypted_data)
    else:
        file_data = encrypted_data

    # 4. Forward to AI Pipeline service
    pipeline_url = f"{settings.AI_PIPELINE_URL}/run"
    try:
        from fastapi.responses import StreamingResponse
        import json
        
        async def event_generator():
            try:
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream(
                        "POST",
                        pipeline_url,
                        data={"report_id": str(report_id)},
                        files={"file": (report.original_filename, file_data, report.mime_type)},
                    ) as response:
                        response.raise_for_status()
                        
                        final_data = None
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            if line.startswith("data: "):
                                yield line + "\n\n"
                                try:
                                    item = json.loads(line[6:])
                                    if item.get("type") == "result":
                                        final_data = item.get("data")
                                except Exception:
                                    pass
                                    
                        if final_data:
                            import copy
                            raw_json_copy = copy.deepcopy(final_data)

                            # Determine the exact report_id returned by the pipeline
                            pipeline_report_id = None
                            if isinstance(final_data, dict):
                                report_meta = final_data.get("report_meta")
                                if isinstance(report_meta, dict):
                                    pipeline_report_id = report_meta.get("report_id") or report_meta.get("title")
                                if not pipeline_report_id:
                                    doc_control = final_data.get("document_control")
                                    if isinstance(doc_control, dict):
                                        pipeline_report_id = doc_control.get("document_id") or doc_control.get("document_title")
                                if not pipeline_report_id:
                                    pipeline_report_id = final_data.get("report_id") or final_data.get("id")

                            if not pipeline_report_id or str(pipeline_report_id).strip().upper() in ("NA", "N/A", "NONE", "NULL", "-", ""):
                                pipeline_report_id = str(report_id)

                            pipeline_report_id = str(pipeline_report_id).strip()

                            # Dispatch multi-threaded background worker for DB persistence,
                            # pgvector chunking, and RAG ingest API call
                            from app.services.rag_worker import dispatch_rag_ingest_job
                            dispatch_rag_ingest_job(
                                db_report_id=report_id,
                                pipeline_report_id=pipeline_report_id,
                                report_data=raw_json_copy,
                            )

                            yield f"data: {json.dumps({'type': 'rag_indexing_dispatched', 'report_id': pipeline_report_id})}\n\n" 
            except httpx.HTTPStatusError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'AI Pipeline service returned an error: {e.response.text}'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to communicate with AI Pipeline service: {str(e)}'})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to setup stream: {str(e)}",
        )

@router.get("/{report_id}/results")
async def get_pipeline_results(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the AI pipeline results for a specific report from the database.
    """
    import os
    import json
    
    # 1. Fetch the report record to check authorization/existence
    report = await report_service.get_report_by_id(db, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found",
        )

    # 2. Fetch main results from ReportsData
    existing_rd_res = await db.execute(select(ReportsData).where(ReportsData.report_id == report_id))
    rd = existing_rd_res.scalar_one_or_none()
    
    if not rd:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pipeline results found for this report",
        )
        
    data = dict(rd.data)
    
    # 3. Stitch detailed observations back in for the frontend API response
    vuln_res = await db.execute(select(DetailedObservation).where(DetailedObservation.report_id == report_id))
    vulns_db = vuln_res.scalars().all()
    
    vuln_list = []
    for v in vulns_db:
        vuln_list.append({
            "report_id": str(v.report_id),
            "finding_id": str(v.finding_id),
            "title": v.title or "",
            "status": v.status.value if v.status else "",
            "severity": v.severity.value if v.severity else "",
            "impact_level": v.impact_level.value if v.impact_level else "",
            "likelihood_level": v.likelihood_level.value if v.likelihood_level else "",
            "cve_id": v.cve_id or [],
            "cvss_score": float(v.cvss_score) if v.cvss_score is not None else None,
            "cvss_vector": v.cvss_vector or "",
            "severity_rationale": v.severity_rationale or "",
            "reported_epss_score": float(v.reported_epss_score) if v.reported_epss_score is not None else None,
            "observation_date": v.observation_date.isoformat() if v.observation_date else "",
            "cwe": v.cwe or [],
            "affected_asset": v.affected_asset or [],
            "regulatory_references": v.regulatory_references or [],
            "observation_description": v.observation_description or "",
            "preconditions": v.preconditions or "",
            "proof_of_concept": v.proof_of_concept or [],
            "impact": v.impact or "",
            "likely_root_cause": v.likely_root_cause or "",
            "recommendation": v.recommendation or "",
            "reference": v.reference or "",
            "new_or_repeat": v.new_or_repeat.value if v.new_or_repeat else "",
            "additional meta": v.meta_data or {}
        })
    data["detailed_observations"] = vuln_list
    
    # 4. Re-order keys exactly as masterjson structure
    master_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../masterjson strcture.json"))
    try:
        with open(master_path, 'r', encoding='utf-8') as f:
            master_json = json.load(f)
            
        def order_dict(data_dict, template_dict):
            ordered = {}
            for k in template_dict.keys():
                if k in data_dict:
                    if isinstance(data_dict[k], dict) and isinstance(template_dict[k], dict):
                        ordered[k] = order_dict(data_dict[k], template_dict[k])
                    elif isinstance(data_dict[k], list) and isinstance(template_dict[k], list) and len(template_dict[k]) > 0 and isinstance(template_dict[k][0], dict):
                        ordered_list = []
                        for item in data_dict[k]:
                            if isinstance(item, dict):
                                ordered_list.append(order_dict(item, template_dict[k][0]))
                            else:
                                ordered_list.append(item)
                        ordered[k] = ordered_list
                    else:
                        ordered[k] = data_dict[k]
            for k in data_dict.keys():
                if k not in ordered:
                    ordered[k] = data_dict[k]
            return ordered
            
        final_data = order_dict(data, master_json)
    except Exception as e:
        final_data = data

    return JSONResponse(content=final_data)
