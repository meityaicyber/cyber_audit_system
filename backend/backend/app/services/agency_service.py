import uuid
from typing import Optional, List, Tuple

from sqlalchemy import select, func, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agency import Agency
from app.schemas.agency import AgencyCreate, AgencyUpdate


async def get_agencies(
    db: AsyncSession, skip: int = 0, limit: int = 50
) -> Tuple[List[Agency], int]:
    """Get paginated list of agencies."""
    count_result = await db.execute(select(func.count(Agency.agency_id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(Agency)
        .order_by(Agency.agency_name)
        .offset(skip)
        .limit(limit)
    )
    agencies = result.scalars().all()

    return list(agencies), total


async def get_agency_by_id(db: AsyncSession, agency_id: uuid.UUID) -> Optional[Agency]:
    """Get a single agency by ID."""
    result = await db.execute(
        select(Agency).where(Agency.agency_id == agency_id)
    )
    return result.scalar_one_or_none()


async def create_agency(db: AsyncSession, agency_in: AgencyCreate) -> Agency:
    """Create a new agency."""
    # Check existing agency_code or registration_number
    conditions = [Agency.agency_code == agency_in.agency_code]
    if agency_in.registration_number:
        conditions.append(Agency.registration_number == agency_in.registration_number)
        
    existing = await db.execute(select(Agency).where(or_(*conditions)))
    if existing.scalar_one_or_none():
        raise ValueError("Agency with this code or registration number already exists")

    agency_data = agency_in.model_dump()
    agency = Agency(**agency_data)
    
    db.add(agency)
    await db.flush()
    return agency


async def update_agency(
    db: AsyncSession, agency_id: uuid.UUID, agency_in: AgencyUpdate
) -> Optional[Agency]:
    """Update an existing agency."""
    agency = await get_agency_by_id(db, agency_id)
    if not agency:
        return None

    update_data = agency_in.model_dump(exclude_unset=True)
    
    if 'registration_number' in update_data and update_data['registration_number']:
        existing = await db.execute(
            select(Agency)
            .where(Agency.registration_number == update_data['registration_number'])
            .where(Agency.agency_id != agency_id)
        )
        if existing.scalar_one_or_none():
            raise ValueError("Agency with this registration number already exists")

    for field, value in update_data.items():
        setattr(agency, field, value)

    await db.flush()
    return agency


async def delete_agency(db: AsyncSession, agency_id: uuid.UUID) -> bool:
    """Delete an agency."""
    agency = await get_agency_by_id(db, agency_id)
    if not agency:
        return False
    
    await db.execute(delete(Agency).where(Agency.agency_id == agency_id))
    await db.flush()
    return True

async def get_agency_stats(db: AsyncSession, agency_id: uuid.UUID) -> dict:
    """Get statistics for an agency, such as total associated reports."""
    from app.models.report import Report
    result = await db.execute(
        select(func.count(Report.report_id)).where(Report.agency_id == agency_id)
    )
    total_reports = result.scalar() or 0
    return {"total_reports": total_reports}
