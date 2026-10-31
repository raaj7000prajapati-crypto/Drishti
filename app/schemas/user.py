from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.user import Role

class UserBase(BaseModel):
    email: str
    full_name: str
    phone: Optional[str] = None
    role: Role = Role.COMPLAINANT
    bureau_id: Optional[int] = None

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    phone: Optional[str] = None
    role: Role = Role.COMPLAINANT
    bureau_id: Optional[int] = None

class UserLogin(BaseModel):
    email: str
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None
    bureau_id: Optional[int] = None
    role: Optional[Role] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    bureau_name: Optional[str] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    type: Optional[str] = None
