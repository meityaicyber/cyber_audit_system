from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func, case, literal_column, text, cast, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import DetailedObservation, ReportsData, ObservationSeverity, ObservationStatus, Report


def apply_orm_filters(query, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None):
    from datetime import datetime, timedelta, timezone
    if report_id:
        query = query.where(DetailedObservation.report_id == report_id)
    elif agency_id:
        query = query.join(Report, DetailedObservation.report_id == Report.report_id).where(Report.agency_id == agency_id)
        
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
                if s.upper() == "INFORMATIONAL":
                    mapped_sev.append("Informational") # If not in enum, fallback string (though type is Enum)
                else:
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
                # Handle edge cases like PARTIALLY_REMEDIATED
                if s.upper() == 'PARTIALLY REMEDIATED' or s.upper() == 'PARTIALLY_REMEDIATED':
                    mapped_status.append(ObservationStatus.PARTIALLY_REMEDIATED)
        if mapped_status:
            query = query.where(DetailedObservation.status.in_(mapped_status))
        
    return query


def apply_raw_filters(where_clauses, params, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None):
    if time_range and time_range != 'ALL':
        days = 0
        if time_range == '30_DAYS': days = 30
        elif time_range == '6_MONTHS': days = 180
        elif time_range == '1_YEAR': days = 365
        if days > 0:
            where_clauses.append(f"v.created_at >= (CURRENT_TIMESTAMP - INTERVAL '{days} days')")

    if severities:
        mapped_sev = []
        for s in severities:
            if s.upper() == "INFORMATIONAL":
                mapped_sev.append("Informational")
            else:
                try:
                    mapped_sev.append(ObservationSeverity[s.upper()].value)
                except KeyError:
                    pass
        if mapped_sev:
            placeholders = []
            for i, s in enumerate(mapped_sev):
                key = f"sev_{i}"
                placeholders.append(f":{key}")
                params[key] = s
            if placeholders:
                where_clauses.append(f"v.severity IN ({','.join(placeholders)})")

    if statuses:
        mapped_status = []
        for s in statuses:
            try:
                mapped_status.append(ObservationStatus[s.upper()].value)
            except KeyError:
                if s.upper() == 'PARTIALLY REMEDIATED' or s.upper() == 'PARTIALLY_REMEDIATED':
                    mapped_status.append(ObservationStatus.PARTIALLY_REMEDIATED.value)
        if mapped_status:
            placeholders = []
            for i, s in enumerate(mapped_status):
                key = f"stat_{i}"
                placeholders.append(f":{key}")
                params[key] = s
            if placeholders:
                where_clauses.append(f"v.status IN ({','.join(placeholders)})")


async def get_summary(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> dict:
    """Get high-level vulnerability analytics summary."""
    # Total detailed_observations
    total_query = select(func.count(DetailedObservation.finding_id))
    total_query = apply_orm_filters(total_query, agency_id, report_id, time_range, severities, statuses)
    total_result = await db.execute(total_query)
    total_detailed_observations = total_result.scalar() or 0

    # Open detailed_observations
    open_query = select(func.count(DetailedObservation.finding_id)).where(DetailedObservation.status == ObservationStatus.OPEN)
    open_query = apply_orm_filters(open_query, agency_id, report_id, time_range, severities, statuses)
    open_result = await db.execute(open_query)
    open_detailed_observations = open_result.scalar() or 0

    # Closed detailed_observations
    closed_query = select(func.count(DetailedObservation.finding_id)).where(DetailedObservation.status == ObservationStatus.CLOSED)
    closed_query = apply_orm_filters(closed_query, agency_id, report_id, time_range, severities, statuses)
    closed_result = await db.execute(closed_query)
    closed_detailed_observations = closed_result.scalar() or 0

    # Average CVSS score
    avg_query = select(func.avg(DetailedObservation.cvss_score)).where(DetailedObservation.cvss_score.isnot(None))
    avg_query = apply_orm_filters(avg_query, agency_id, report_id, time_range, severities, statuses)
    avg_result = await db.execute(avg_query)
    avg_cvss = avg_result.scalar()
    avg_cvss_score = round(float(avg_cvss), 1) if avg_cvss is not None else None

    # Severity counts
    severity_counts = {}
    for level in ObservationSeverity:
        count_query = select(func.count(DetailedObservation.finding_id)).where(DetailedObservation.severity == level)
        count_query = apply_orm_filters(count_query, agency_id, report_id, time_range, severities, statuses)
        count_result = await db.execute(count_query)
        severity_counts[level.value] = count_result.scalar() or 0

    # Reports with detailed_observations
    reports_query = select(func.count(func.distinct(DetailedObservation.report_id)))
    reports_query = apply_orm_filters(reports_query, agency_id, report_id, time_range, severities, statuses)
    reports_result = await db.execute(reports_query)
    reports_with_detailed_observations = reports_result.scalar() or 0

    return {
        "total_detailed_observations": total_detailed_observations,
        "open_detailed_observations": open_detailed_observations,
        "closed_detailed_observations": closed_detailed_observations,
        "avg_cvss_score": avg_cvss_score,
        "critical_count": severity_counts.get("Critical", 0),
        "high_count": severity_counts.get("High", 0),
        "medium_count": severity_counts.get("Medium", 0),
        "low_count": severity_counts.get("Low", 0),
        "informational_count": severity_counts.get("Informational", 0),
        "reports_with_detailed_observations": reports_with_detailed_observations,
    }


async def get_severity_distribution(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get vulnerability count per severity level."""
    query = select(
        cast(DetailedObservation.severity, String).label("severity"),
        func.count(DetailedObservation.finding_id).label("count"),
    ).where(DetailedObservation.severity.isnot(None))
    
    query = apply_orm_filters(query, agency_id, report_id, time_range, severities, statuses)
    query = query.group_by(DetailedObservation.severity).order_by(func.count(DetailedObservation.finding_id).desc())
    
    result = await db.execute(query)
    rows = result.all()

    # Ensure all severity levels appear, even with 0 count
    severity_order = ["Critical", "High", "Medium", "Low", "Informational"]
    counts_map = {}
    for row in rows:
        val = getattr(row.severity, 'value', str(row.severity)).split('.')[-1].upper()
        counts_map[val] = row.count
    return [
        {"severity": s.upper(), "count": counts_map.get(s.upper(), 0)}
        for s in severity_order
    ]


async def get_status_distribution(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get vulnerability count per status."""
    query = select(
        cast(DetailedObservation.status, String).label("status"),
        func.count(DetailedObservation.finding_id).label("count"),
    ).where(DetailedObservation.status.isnot(None))

    query = apply_orm_filters(query, agency_id, report_id, time_range, severities, statuses)
    query = query.group_by(DetailedObservation.status).order_by(func.count(DetailedObservation.finding_id).desc())

    result = await db.execute(query)
    rows = result.all()

    # Ensure all statuses appear
    status_order = ["Open", "Closed", "Partially Remediated"]
    counts_map = {}
    for row in rows:
        val = getattr(row.status, 'value', str(row.status)).split('.')[-1].upper()
        counts_map[val] = row.count
    return [
        {"status": s.upper(), "count": counts_map.get(s.upper(), 0)}
        for s in status_order
    ]


async def get_cvss_distribution(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get CVSS score histogram buckets."""
    buckets = []
    ranges = [
        ("0-1", 0.0, 1.0),
        ("1-2", 1.0, 2.0),
        ("2-3", 2.0, 3.0),
        ("3-4", 3.0, 4.0),
        ("4-5", 4.0, 5.0),
        ("5-6", 5.0, 6.0),
        ("6-7", 6.0, 7.0),
        ("7-8", 7.0, 8.0),
        ("8-9", 8.0, 9.0),
        ("9-10", 9.0, 10.1),  # inclusive of 10.0
    ]

    for label, low, high in ranges:
        query = select(func.count(DetailedObservation.finding_id)).where(
            DetailedObservation.cvss_score.isnot(None),
            DetailedObservation.cvss_score >= low,
            DetailedObservation.cvss_score < high,
        )
        query = apply_orm_filters(query, agency_id, report_id, time_range, severities, statuses)
        result = await db.execute(query)
        count = result.scalar() or 0
        buckets.append({"range": label, "count": count})

    return buckets


async def get_category_breakdown(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get top 15 vulnerability categories by count."""
    query = select(
        DetailedObservation.impact_level,
        func.count(DetailedObservation.finding_id).label("count"),
    # `impact_level` is a PostgreSQL enum, so comparing it to an empty string
    # causes asyncpg to reject the bound value as an invalid enum member.
    ).where(DetailedObservation.impact_level.isnot(None))
    
    query = apply_orm_filters(query, agency_id, report_id, time_range, severities, statuses)
    query = query.group_by(DetailedObservation.impact_level).order_by(func.count(DetailedObservation.finding_id).desc()).limit(15)

    result = await db.execute(query)
    rows = result.all()
    return [{"impact_level": row.impact_level, "count": row.count} for row in rows]


async def get_trend(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get vulnerability count by month (last 12 months) based on reports_data.report_date."""
    # Use raw SQL for date_trunc which is PostgreSQL specific
    base_sql = """
        SELECT
            to_char(date_trunc('month', v.created_at), 'YYYY-MM') AS month,
            COUNT(v.finding_id) AS count
        FROM detailed_observations v
        JOIN reports_data rd ON v.report_id = rd.report_id
    """
    
    where_clauses = [
        "v.created_at >= (CURRENT_DATE - INTERVAL '12 months')",
        "v.created_at IS NOT NULL"
    ]
    params = {}
    
    if report_id:
        where_clauses.append("v.report_id = :report_id")
        params["report_id"] = str(report_id)
    elif agency_id:
        base_sql += " JOIN reports r ON v.report_id = r.report_id "
        where_clauses.append("r.agency_id = :agency_id")
        params["agency_id"] = str(agency_id)
        
    apply_raw_filters(where_clauses, params, time_range, severities, statuses)
        
    sql_query = base_sql + " WHERE " + " AND ".join(where_clauses) + """
        GROUP BY date_trunc('month', v.created_at)
        ORDER BY date_trunc('month', v.created_at)
    """

    result = await db.execute(text(sql_query), params)
    rows = result.all()
    return [{"month": row.month, "count": row.count} for row in rows]


async def get_top_cwe(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get top 10 CWE IDs by frequency (unnest the cwe array)."""
    base_sql = """
        SELECT cwe_item.cwe_id, COUNT(*) AS count
        FROM detailed_observations AS v
    """
    
    where_clauses = ["v.cwe IS NOT NULL"]
    params = {}
    
    if report_id:
        where_clauses.append("v.report_id = :report_id")
        params["report_id"] = str(report_id)
    elif agency_id:
        base_sql += " JOIN reports AS r ON v.report_id = r.report_id "
        where_clauses.append("r.agency_id = :agency_id")
        params["agency_id"] = str(agency_id)

    apply_raw_filters(where_clauses, params, time_range, severities, statuses)

    base_sql += " CROSS JOIN LATERAL unnest(v.cwe) AS cwe_item(cwe_id) "
    sql_query = base_sql + " WHERE " + " AND ".join(where_clauses) + """
        GROUP BY cwe_item.cwe_id
        ORDER BY count DESC
        LIMIT 10
    """
    
    result = await db.execute(text(sql_query), params)
    rows = result.all()
    return [{"cwe_id": row.cwe_id, "count": row.count} for row in rows]


async def get_top_cve(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get top 10 CVE IDs by frequency (unnest the cve_id array)."""
    base_sql = """
        SELECT cve_item.cve_id, COUNT(*) AS count
        FROM detailed_observations AS v
    """
    
    where_clauses = ["v.cve_id IS NOT NULL"]
    params = {}
    
    if report_id:
        where_clauses.append("v.report_id = :report_id")
        params["report_id"] = str(report_id)
    elif agency_id:
        base_sql += " JOIN reports AS r ON v.report_id = r.report_id "
        where_clauses.append("r.agency_id = :agency_id")
        params["agency_id"] = str(agency_id)

    apply_raw_filters(where_clauses, params, time_range, severities, statuses)

    base_sql += " CROSS JOIN LATERAL unnest(v.cve_id) AS cve_item(cve_id) "
    sql_query = base_sql + " WHERE " + " AND ".join(where_clauses) + """
        GROUP BY cve_item.cve_id
        ORDER BY count DESC
        LIMIT 10
    """

    result = await db.execute(text(sql_query), params)
    rows = result.all()
    return [{"cve_id": row.cve_id, "count": row.count} for row in rows]


async def get_affected_assets(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get top 15 most-attacked assets (unnest the affected_asset array)."""
    base_sql = """
        SELECT asset_item.asset, COUNT(*) AS count
        FROM detailed_observations AS v
    """
    
    where_clauses = ["v.affected_asset IS NOT NULL"]
    params = {}
    
    if report_id:
        where_clauses.append("v.report_id = :report_id")
        params["report_id"] = str(report_id)
    elif agency_id:
        base_sql += " JOIN reports AS r ON v.report_id = r.report_id "
        where_clauses.append("r.agency_id = :agency_id")
        params["agency_id"] = str(agency_id)

    apply_raw_filters(where_clauses, params, time_range, severities, statuses)

    base_sql += " CROSS JOIN LATERAL unnest(v.affected_asset) AS asset_item(asset) "
    sql_query = base_sql + " WHERE " + " AND ".join(where_clauses) + """
        GROUP BY asset_item.asset
        ORDER BY count DESC
        LIMIT 15
    """

    result = await db.execute(text(sql_query), params)
    rows = result.all()
    return [{"asset": row.asset, "count": row.count} for row in rows]


async def get_new_vs_repeat(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get count of New vs Repeat findings."""
    query = select(
        DetailedObservation.new_or_repeat,
        func.count(DetailedObservation.finding_id).label("count"),
    ).where(
        DetailedObservation.new_or_repeat.isnot(None),
    )

    query = apply_orm_filters(query, agency_id, report_id, time_range, severities, statuses)
    query = query.group_by(DetailedObservation.new_or_repeat).order_by(func.count(DetailedObservation.finding_id).desc())

    result = await db.execute(query)
    rows = result.all()
    return [{"type": row.new_or_repeat, "count": row.count} for row in rows]


async def get_recent_vulns(db: AsyncSession, agency_id: Optional[UUID] = None, report_id: Optional[UUID] = None, time_range: Optional[str] = None, severities: Optional[list] = None, statuses: Optional[list] = None) -> list:
    """Get the latest 10 detailed_observations."""
    query = select(DetailedObservation)
    query = apply_orm_filters(query, agency_id, report_id, time_range, severities, statuses)
    query = query.order_by(DetailedObservation.created_at.desc()).limit(10)

    result = await db.execute(query)
    vulns = result.scalars().all()
    return [
        {
            "finding_id": str(v.finding_id),
            "report_id": str(v.report_id),
            "title": v.title,
            "severity": v.severity.value if v.severity else None,
            "status": v.status.value if v.status else None,
            "cvss_score": float(v.cvss_score) if v.cvss_score is not None else None,
            "impact_level": v.impact_level,
            "created_at": v.created_at.isoformat(),
        }
        for v in vulns
    ]
