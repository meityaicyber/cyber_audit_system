from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID


class RoleOut(BaseModel):
    role_id: int
    role_name: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    roles: List[str] = Field(default=["AUDITOR"])


class UserUpdate(BaseModel):
    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None


class UserOut(BaseModel):
    user_id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: List[str] = []

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_roles(cls, user):
        role_names = [ur.role.role_name for ur in user.roles] if user.roles else []
        return cls(
            user_id=user.user_id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=role_names,
        )


class UserListOut(BaseModel):
    users: List[UserOut]
    total: int


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
