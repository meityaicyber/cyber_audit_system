from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.services import analytics_service
from app.schemas.analytics import (
    AnalyticsSummary,
    SeverityDistribution,
    SeverityItem,
    StatusDistribution,
    StatusItem,
    CvssDistribution,
    CvssBucket,
    CategoryBreakdown,
    CategoryItem,
    VulnTrend,
    TrendItem,
    TopCwe,
    CweItem,
    TopCve,
    CveItem,
    AffectedAssets,
    AssetItem,
    NewVsRepeat,
    NewVsRepeatItem,
    RecentVulns,
    RecentVuln,
)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get high-level vulnerability analytics summary."""
    data = await analytics_service.get_summary(db, agency_id, report_id)
    return AnalyticsSummary(**data)


@router.get("/severity-distribution", response_model=SeverityDistribution)
async def get_severity_distribution(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get vulnerability count per severity level."""
    items = await analytics_service.get_severity_distribution(db, agency_id, report_id)
    return SeverityDistribution(data=[SeverityItem(**i) for i in items])


@router.get("/status-distribution", response_model=StatusDistribution)
async def get_status_distribution(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get vulnerability count per status."""
    items = await analytics_service.get_status_distribution(db, agency_id, report_id)
    return StatusDistribution(data=[StatusItem(**i) for i in items])


@router.get("/cvss-distribution", response_model=CvssDistribution)
async def get_cvss_distribution(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get CVSS score histogram buckets."""
    items = await analytics_service.get_cvss_distribution(db, agency_id, report_id)
    return CvssDistribution(data=[CvssBucket(**i) for i in items])


@router.get("/impact_level-breakdown", response_model=CategoryBreakdown)
async def get_category_breakdown(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top vulnerability categories by count."""
    items = await analytics_service.get_category_breakdown(db, agency_id, report_id)
    return CategoryBreakdown(data=[CategoryItem(**i) for i in items])


@router.get("/trend", response_model=VulnTrend)
async def get_trend(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get vulnerability count by month (last 12 months)."""
    items = await analytics_service.get_trend(db, agency_id, report_id)
    return VulnTrend(data=[TrendItem(**i) for i in items])


@router.get("/top-cwe", response_model=TopCwe)
async def get_top_cwe(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top 10 CWE IDs by frequency."""
    items = await analytics_service.get_top_cwe(db, agency_id, report_id)
    return TopCwe(data=[CweItem(**i) for i in items])


@router.get("/top-cve", response_model=TopCve)
async def get_top_cve(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top 10 CVE IDs by frequency."""
    items = await analytics_service.get_top_cve(db, agency_id, report_id)
    return TopCve(data=[CveItem(**i) for i in items])


@router.get("/affected-assets", response_model=AffectedAssets)
async def get_affected_assets(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get top most-attacked assets."""
    items = await analytics_service.get_affected_assets(db, agency_id, report_id)
    return AffectedAssets(data=[AssetItem(**i) for i in items])


@router.get("/new-vs-repeat", response_model=NewVsRepeat)
async def get_new_vs_repeat(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of New vs Repeat findings."""
    items = await analytics_service.get_new_vs_repeat(db, agency_id, report_id)
    return NewVsRepeat(data=[NewVsRepeatItem(**i) for i in items])


@router.get("/recent-vulns", response_model=RecentVulns)
async def get_recent_vulns(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get latest 10 vulnerabilities."""
    items = await analytics_service.get_recent_vulns(db, agency_id, report_id)
    return RecentVulns(data=[RecentVuln(**i) for i in items])
@router.get("/vulnerabilities-raw")
async def get_all_vulnerabilities_raw(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    time_range: Optional[str] = Query('ALL'),
    severities: list[str] = Query(None),
    statuses: list[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    from app.models.report import DetailedObservation, Report, ObservationSeverity, ObservationStatus
    from datetime import datetime, timedelta, timezone

    query = select(DetailedObservation, Report.agency_id).join(Report, DetailedObservation.report_id == Report.report_id)
    
    if report_id:
        query = query.where(DetailedObservation.report_id == report_id)
    if agency_id:
        query = query.where(Report.agency_id == agency_id)
        
    if time_range and time_range != 'ALL':
        days = 0
        if time_range == '30_DAYS': days = 30
        elif time_range == '6_MONTHS': days = 180
        elif time_range == '1_YEAR': days = 365
        if days > 0:
            threshold = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.where(DetailedObservation.created_at >= threshold)
            
    if severities:
        mapped_sev = []
        for s in severities:
            try:
                mapped_sev.append(ObservationSeverity[s.upper()])
            except KeyError:
                pass
        if mapped_sev:
            query = query.where(DetailedObservation.severity.in_(mapped_sev))
        
    if statuses:
        mapped_status = []
        for s in statuses:
            try:
                mapped_status.append(ObservationStatus[s.upper()])
            except KeyError:
                if s.upper() == 'PARTIALLY REMEDIATED' or s.upper() == 'PARTIALLY_REMEDIATED':
                    mapped_status.append(ObservationStatus.PARTIALLY_REMEDIATED)
        if mapped_status:
            query = query.where(DetailedObservation.status.in_(mapped_status))
        
    # Get total count for pagination
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
        
    # Apply pagination and sorting
    query = query.order_by(DetailedObservation.created_at.desc()).offset((page - 1) * limit).limit(limit)
        
    result = await db.execute(query)
    rows = result.all()
    
    data = []
    for vuln, ag_id in rows:
        data.append({
            "id": str(vuln.finding_id),
            "title": vuln.title,
            "severity": vuln.severity.value if vuln.severity else None,
            "status": vuln.status.value if vuln.status else None,
            "cvss": float(vuln.cvss_score) if vuln.cvss_score is not None else None,
            "date": vuln.created_at.isoformat(),
            "impact_level": vuln.impact_level,
            "cwe": vuln.cwe[0] if vuln.cwe and len(vuln.cwe) > 0 else None,
            "cve": vuln.cve_id[0] if vuln.cve_id and len(vuln.cve_id) > 0 else None,
            "asset": vuln.affected_asset[0] if vuln.affected_asset and len(vuln.affected_asset) > 0 else None,
            "new_or_repeat": vuln.new_or_repeat,
            "reportId": str(vuln.report_id),
            "agencyId": str(ag_id) if ag_id else None
        })
    return {"count": total, "page": page, "limit": limit, "data": data}


import asyncio

@router.get("/dashboard-aggregates")
async def get_dashboard_aggregates(
    agency_id: Optional[UUID] = None,
    report_id: Optional[UUID] = None,
    time_range: Optional[str] = Query('ALL'),
    severities: list[str] = Query(None),
    statuses: list[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch all dashboard analytics in a single highly-optimized payload."""
    summary = await analytics_service.get_summary(db, agency_id, report_id, time_range, severities, statuses)
    severity_dist = await analytics_service.get_severity_distribution(db, agency_id, report_id, time_range, severities, statuses)
    status_dist = await analytics_service.get_status_distribution(db, agency_id, report_id, time_range, severities, statuses)
    cvss_dist = await analytics_service.get_cvss_distribution(db, agency_id, report_id, time_range, severities, statuses)
    trend = await analytics_service.get_trend(db, agency_id, report_id, time_range, severities, statuses)
    categories = await analytics_service.get_category_breakdown(db, agency_id, report_id, time_range, severities, statuses)
    top_cwe = await analytics_service.get_top_cwe(db, agency_id, report_id, time_range, severities, statuses)
    top_cve = await analytics_service.get_top_cve(db, agency_id, report_id, time_range, severities, statuses)
    affected_assets = await analytics_service.get_affected_assets(db, agency_id, report_id, time_range, severities, statuses)
    new_vs_repeat = await analytics_service.get_new_vs_repeat(db, agency_id, report_id, time_range, severities, statuses)
    
    results = [summary, severity_dist, status_dist, cvss_dist, trend, categories, top_cwe, top_cve, affected_assets, new_vs_repeat]

    return {
        "summary": results[0],
        "severityDist": results[1],
        "statusDist": results[2],
        "cvssDist": results[3],
        "trend": results[4],
        "categories": results[5],
        "topCwe": results[6],
        "topCve": results[7],
        "assets": results[8],
        "newRepeat": results[9]
    }

