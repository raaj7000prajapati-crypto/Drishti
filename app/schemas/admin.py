from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.user import Role

class BureauCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    head_email: Optional[str] = None


class BureauResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    head_email: Optional[str] = None
    is_active: bool
    created_at: datetime
    official_count: Optional[int] = 0
    active_complaints_count: Optional[int] = 0

    class Config:
        from_attributes = True

class RoutingRuleCreate(BaseModel):
    category: Optional[str] = None
    keywords: str
    target_bureau_id: int
    priority: int = 0
    is_active: bool = True

class RoutingRuleUpdate(BaseModel):
    category: Optional[str] = None
    keywords: Optional[str] = None
    target_bureau_id: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None

class RoutingRuleResponse(BaseModel):
    id: int
    category: Optional[str] = None
    keywords: str
    target_bureau_id: int
    target_bureau_name: Optional[str] = None
    priority: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class SLAConfigUpdate(BaseModel):
    max_hours: int
    escalation_level: Optional[str] = "Bureau Head & Admin"

class SLAConfigResponse(BaseModel):
    id: int
    priority: str
    max_hours: int
    escalation_level: str

    class Config:
        from_attributes = True

class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    ip_address: Optional[str] = None
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ReassignComplaintRequest(BaseModel):
    bureau_id: int
    official_id: Optional[int] = None
    reason: Optional[str] = None
