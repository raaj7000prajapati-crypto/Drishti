from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from app.core.database import Base


class CaseGroup(Base):
    __tablename__ = "case_groups"

    id = Column(Integer, primary_key=True, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    created_by = relationship("User")
    memberships = relationship(
        "CaseGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )


class CaseGroupMember(Base):
    __tablename__ = "case_group_members"
    __table_args__ = (
        Index("ix_case_group_members_group_complaint", "case_group_id", "complaint_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    case_group_id = Column(
        Integer,
        ForeignKey("case_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    complaint_id = Column(
        Integer,
        ForeignKey("complaints.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    added_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    group = relationship("CaseGroup", back_populates="memberships")
    complaint = relationship("Complaint", back_populates="case_group_membership")
    added_by = relationship("User", foreign_keys=[added_by_id])
