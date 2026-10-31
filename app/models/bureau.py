from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base

class Bureau(Base):
    __tablename__ = "bureaus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    head_email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    officials = relationship("User", back_populates="bureau", foreign_keys="User.bureau_id")
    complaints = relationship("Complaint", back_populates="bureau", foreign_keys="Complaint.bureau_id")
    routing_rules = relationship("RoutingRule", back_populates="target_bureau", cascade="all, delete-orphan")
