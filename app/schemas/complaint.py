from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel
from app.models.complaint import ComplaintStatus, Priority, Determination

class AttachmentResponse(BaseModel):
    id: int
    file_name: str
    file_size: int
    content_type: str
    uploaded_at: datetime

    class Config:
        from_attributes = True

class EventResponse(BaseModel):
    id: int
    event_type: str
    title: str
    description: Optional[str] = None
    event_metadata: Optional[Any] = None
    created_at: datetime
    actor_name: Optional[str] = None

    class Config:
        from_attributes = True

class InfoRequestResponse(BaseModel):
    id: int
    question: str
    complainant_response: Optional[str] = None
    status: str
    requested_at: datetime
    responded_at: Optional[datetime] = None
    official_name: Optional[str] = None

    class Config:
        from_attributes = True

class AnnotationResponse(BaseModel):
    id: int
    note: str
    attachment_name: Optional[str] = None
    has_attachment: bool = False
    is_internal: bool
    created_at: datetime
    author_name: Optional[str] = None

    class Config:
        from_attributes = True

class CaseLinkResponse(BaseModel):
    id: int
    source_complaint_id: Optional[int] = None
    target_complaint_id: Optional[int] = None
    target_receipt_id: Optional[str] = None
    target_subject: Optional[str] = None
    target_bureau_name: Optional[str] = None
    target_status: Optional[str] = None
    similarity_score: float
    similarity_bucket: str
    shared_keywords: Optional[str] = None
    status: str
    decided_at: Optional[datetime] = None
    decided_by_name: Optional[str] = None

    class Config:
        from_attributes = True

class FeedbackResponse(BaseModel):
    id: int
    rating: int
    comments: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ComplaintCreate(BaseModel):
    institution_name: str
    institution_state: str
    institution_city: str
    category: str
    priority: Priority = Priority.MEDIUM
    subject: str
    description: str

class ComplaintResponse(BaseModel):
    id: int
    receipt_id: str
    institution_name: str
    institution_state: str
    institution_city: str
    category: str
    priority: Priority
    subject: str
    description: str
    status: ComplaintStatus
    determination: Determination
    determination_reason: Optional[str] = None
    bureau_id: Optional[int] = None
    bureau_name: Optional[str] = None
    assigned_official_id: Optional[int] = None
    assigned_official_name: Optional[str] = None
    complainant_name: Optional[str] = None
    sla_due_at: Optional[datetime] = None
    is_overdue: bool
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ComplaintDetailResponse(ComplaintResponse):
    attachments: List[AttachmentResponse] = []
    events: List[EventResponse] = []
    information_requests: List[InfoRequestResponse] = []
    annotations: List[AnnotationResponse] = []
    suggested_links: List[CaseLinkResponse] = []
    feedback: Optional[FeedbackResponse] = None

class StatusUpdate(BaseModel):
    status: ComplaintStatus
    comment: Optional[str] = None

class DeterminationCreate(BaseModel):
    determination: Determination  # Accepted or Rejected
    reason: str

class InfoRequestCreate(BaseModel):
    question: str

class InfoResponseCreate(BaseModel):
    response: str

class AnnotationCreate(BaseModel):
    note: str
    is_internal: bool = True

class FeedbackCreate(BaseModel):
    rating: int
    comments: Optional[str] = None

class DuplicateCheckResult(BaseModel):
    has_potential_duplicate: bool
    message: Optional[str] = None
    matched_count: int = 0
