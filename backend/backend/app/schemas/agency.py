from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional, List, Literal
from datetime import datetime, date
from uuid import UUID

AgencyType = Literal[
    'CERT_IN_EMPANELLED',
    'PRIVATE_AUDITOR',
    'INTERNAL_AUDIT_TEAM',
    'GOVERNMENT_AGENCY',
    'THIRD_PARTY_ASSESSOR'
]

AgencyStatus = Literal[
    'ACTIVE',
    'INACTIVE',
    'SUSPENDED',
    'BLACKLISTED'
]

class AgencyBase(BaseModel):
    agency_code: str = Field(..., max_length=50)
    agency_name: str = Field(..., max_length=255)
    agency_type: AgencyType
    registration_number: Optional[str] = Field(None, max_length=100)
    cert_in_empanelled: bool = False
    empanelment_number: Optional[str] = Field(None, max_length=100)
    empanelment_expiry: Optional[date] = None
    
    contact_person: str = Field(..., max_length=255)
    contact_email: EmailStr
    contact_phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: str = Field('India', max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)
    
    status: AgencyStatus = 'ACTIVE'
    onboarding_date: date = Field(default_factory=date.today)
    remarks: Optional[str] = None


class AgencyCreate(AgencyBase):
    pass


class AgencyUpdate(BaseModel):
    agency_name: Optional[str] = Field(None, max_length=255)
    agency_type: Optional[AgencyType] = None
    registration_number: Optional[str] = Field(None, max_length=100)
    cert_in_empanelled: Optional[bool] = None
    empanelment_number: Optional[str] = Field(None, max_length=100)
    empanelment_expiry: Optional[date] = None
    
    contact_person: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)
    
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    pincode: Optional[str] = Field(None, max_length=20)
    
    status: Optional[AgencyStatus] = None
    onboarding_date: Optional[date] = None
    remarks: Optional[str] = None


class AgencyOut(AgencyBase):
    agency_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgencyListOut(BaseModel):
    agencies: List[AgencyOut]
    total: int

class AgencyStatsOut(BaseModel):
    total_reports: int
