from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class RoutingRule(Base):
    __tablename__ = "routing_rules"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=True, index=True)
    keywords = Column(String(500), nullable=False)  # Comma-separated lowercase keywords
    target_bureau_id = Column(Integer, ForeignKey("bureaus.id", ondelete="CASCADE"), nullable=False)
    priority = Column(Integer, default=0, nullable=False)  # Higher number = higher precedence
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    target_bureau = relationship("Bureau", back_populates="routing_rules")

class SLAConfig(Base):
    __tablename__ = "sla_configs"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(String(20), unique=True, nullable=False)  # Urgent, High, Medium, Low
    max_hours = Column(Integer, nullable=False)
    escalation_level = Column(String(100), default="Bureau Head & Admin", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
