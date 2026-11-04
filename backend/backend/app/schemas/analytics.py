from pydantic import BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime, date
from uuid import UUID


class AnalyticsSummary(BaseModel):
    total_detailed_observations: int
    open_detailed_observations: int
    closed_detailed_observations: int
    avg_cvss_score: Optional[float] = None
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    informational_count: int
    reports_with_detailed_observations: int


class SeverityItem(BaseModel):
    severity: str
    count: int


class SeverityDistribution(BaseModel):
    data: List[SeverityItem]


class StatusItem(BaseModel):
    status: str
    count: int


class StatusDistribution(BaseModel):
    data: List[StatusItem]


class CvssBucket(BaseModel):
    range: str
    count: int


class CvssDistribution(BaseModel):
    data: List[CvssBucket]


class CategoryItem(BaseModel):
    impact_level: str
    count: int


class CategoryBreakdown(BaseModel):
    data: List[CategoryItem]


class TrendItem(BaseModel):
    month: str
    count: int


class VulnTrend(BaseModel):
    data: List[TrendItem]


class CweItem(BaseModel):
    cwe_id: str
    count: int


class TopCwe(BaseModel):
    data: List[CweItem]


class CveItem(BaseModel):
    cve_id: str
    count: int


class TopCve(BaseModel):
    data: List[CveItem]


class AssetItem(BaseModel):
    asset: str
    count: int


class AffectedAssets(BaseModel):
    data: List[AssetItem]


class NewVsRepeatItem(BaseModel):
    type: str
    count: int


class NewVsRepeat(BaseModel):
    data: List[NewVsRepeatItem]


class RecentVuln(BaseModel):
    finding_id: UUID
    report_id: UUID
    title: str
    severity: Optional[str] = None
    status: Optional[str] = None
    cvss_score: Optional[float] = None
    impact_level: Optional[str] = None
    created_at: datetime


class RecentVulns(BaseModel):
    data: List[RecentVuln]
