import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Enum, 
    ForeignKey, Float, JSON
)
from sqlalchemy.orm import relationship
from app.core.database import Base

class ComplaintStatus(str, enum.Enum):
    NEW = "New"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    AWAITING_INFO = "Awaiting Info"
    OVERDUE = "Overdue"
    CLOSED = "Closed"

class Priority(str, enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    URGENT = "Urgent"

class Determination(str, enum.Enum):
    NONE = "None"
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(String(30), unique=True, index=True, nullable=False)
    complainant_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    institution_name = Column(String(255), nullable=False, index=True)
    institution_state = Column(String(100), nullable=False)
    institution_city = Column(String(100), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    priority = Column(Enum(Priority), default=Priority.MEDIUM, nullable=False, index=True)
    
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    status = Column(Enum(ComplaintStatus), default=ComplaintStatus.NEW, nullable=False, index=True)
    determination = Column(Enum(Determination), default=Determination.NONE, nullable=False)
    determination_reason = Column(Text, nullable=True)
    
    bureau_id = Column(Integer, ForeignKey("bureaus.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_official_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    sla_due_at = Column(DateTime, nullable=True, index=True)
    is_overdue = Column(Boolean, default=False, nullable=False, index=True)
    is_archived = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    complainant = relationship("User", back_populates="complaints", foreign_keys=[complainant_id])
    assigned_official = relationship("User", back_populates="assigned_complaints", foreign_keys=[assigned_official_id])
    bureau = relationship("Bureau", back_populates="complaints", foreign_keys=[bureau_id])
    
    attachments = relationship("ComplaintAttachment", back_populates="complaint", cascade="all, delete-orphan")
    events = relationship("ComplaintEvent", back_populates="complaint", order_by="ComplaintEvent.created_at.asc()", cascade="all, delete-orphan")
    information_requests = relationship("InformationRequest", back_populates="complaint", cascade="all, delete-orphan")
    annotations = relationship("Annotation", back_populates="complaint", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="complaint", uselist=False, cascade="all, delete-orphan")
    embedding = relationship("ComplaintEmbedding", back_populates="complaint", uselist=False, cascade="all, delete-orphan")
    
    source_links = relationship("CaseLink", foreign_keys="CaseLink.source_complaint_id", back_populates="source_complaint", cascade="all, delete-orphan")
    target_links = relationship("CaseLink", foreign_keys="CaseLink.target_complaint_id", back_populates="target_complaint", cascade="all, delete-orphan")
    case_group_membership = relationship(
        "CaseGroupMember",
        back_populates="complaint",
        uselist=False,
        cascade="all, delete-orphan",
    )

class ComplaintAttachment(Base):
    __tablename__ = "complaint_attachments"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    content_type = Column(String(100), nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    complaint = relationship("Complaint", back_populates="attachments")

class ComplaintEvent(Base):
    __tablename__ = "complaint_events"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    event_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    complaint = relationship("Complaint", back_populates="events")
    actor = relationship("User")

class InformationRequest(Base):
    __tablename__ = "information_requests"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    official_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    question = Column(Text, nullable=False)
    complainant_response = Column(Text, nullable=True)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, RESPONDED
    requested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    responded_at = Column(DateTime, nullable=True)

    complaint = relationship("Complaint", back_populates="information_requests")
    official = relationship("User", foreign_keys=[official_id])

class Annotation(Base):
    __tablename__ = "annotations"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=False)
    attachment_name = Column(String(255), nullable=True)
    attachment_stored_name = Column(String(255), nullable=True)
    is_internal = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    complaint = relationship("Complaint", back_populates="annotations")
    author = relationship("User", foreign_keys=[author_id])

class CaseLink(Base):
    __tablename__ = "case_links"

    id = Column(Integer, primary_key=True, index=True)
    source_complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    target_complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score = Column(Float, nullable=False)
    similarity_bucket = Column(String(20), nullable=False)  # High, Medium, Low, Minimal
    shared_keywords = Column(Text, nullable=True)
    status = Column(String(20), default="SUGGESTED", nullable=False)  # SUGGESTED, CONFIRMED, REJECTED
    decided_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    source_complaint = relationship("Complaint", foreign_keys=[source_complaint_id], back_populates="source_links")
    target_complaint = relationship("Complaint", foreign_keys=[target_complaint_id], back_populates="target_links")
    decided_by = relationship("User", foreign_keys=[decided_by_id])

class ComplaintEmbedding(Base):
    __tablename__ = "complaint_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    model_name = Column(String(100), nullable=False)
    vector_json = Column(Text, nullable=False)  # Serialized list of floats
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    complaint = relationship("Complaint", back_populates="embedding")
