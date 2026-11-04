from pydantic import BaseModel, Field
from typing import Optional, List


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenData(BaseModel):
    sub: Optional[str] = None
    roles: List[str] = []
    type: Optional[str] = None
    session_id: Optional[str] = None
