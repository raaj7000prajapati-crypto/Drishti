import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Role(str, enum.Enum):
    COMPLAINANT = "COMPLAINANT"
    OFFICIAL = "OFFICIAL"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(Enum(Role), default=Role.COMPLAINANT, nullable=False, index=True)
    bureau_id = Column(Integer, ForeignKey("bureaus.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    bureau = relationship("Bureau", back_populates="officials", foreign_keys=[bureau_id])
    complaints = relationship("Complaint", back_populates="complainant", foreign_keys="Complaint.complainant_id")
    assigned_complaints = relationship("Complaint", back_populates="assigned_official", foreign_keys="Complaint.assigned_official_id")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
