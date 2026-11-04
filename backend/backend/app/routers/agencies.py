import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models.user import User
from app.schemas.agency import AgencyCreate, AgencyUpdate, AgencyOut, AgencyListOut, AgencyStatsOut
from app.services import agency_service

router = APIRouter(prefix="/api/agencies", tags=["Agencies"])


@router.post("", response_model=AgencyOut, status_code=status.HTTP_201_CREATED)
async def create_agency(
    agency_in: AgencyCreate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new agency (admin only)."""
    try:
        agency = await agency_service.create_agency(db, agency_in)
        return agency
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("", response_model=AgencyListOut)
async def list_agencies(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all agencies."""
    agencies, total = await agency_service.get_agencies(db, skip=skip, limit=limit)
    return AgencyListOut(agencies=agencies, total=total)


@router.get("/{agency_id}", response_model=AgencyOut)
async def get_agency(
    agency_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single agency."""
    agency = await agency_service.get_agency_by_id(db, agency_id)
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    return agency


@router.get("/{agency_id}/stats", response_model=AgencyStatsOut)
async def get_agency_stats(
    agency_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics for a single agency."""
    agency = await agency_service.get_agency_by_id(db, agency_id)
    if not agency:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
    stats = await agency_service.get_agency_stats(db, agency_id)
    return stats

@router.put("/{agency_id}", response_model=AgencyOut)
async def update_agency(
    agency_id: uuid.UUID,
    agency_in: AgencyUpdate,
    current_user: User = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Update an agency (admin only)."""
    try:
        agency = await agency_service.update_agency(db, agency_id, agency_in)
        if not agency:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
        return agency
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{agency_id}", status_code=status.HTTP_200_OK)
async def delete_agency(
    agency_id: uuid.UUID,
    current_user: User = Depends(require_roles("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Delete an agency (admin only)."""
    try:
        success = await agency_service.delete_agency(db, agency_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency not found")
        return {"message": "Agency deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
