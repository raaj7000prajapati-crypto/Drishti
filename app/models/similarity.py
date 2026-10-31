from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer

from app.core.database import Base


class SimilarityThresholdConfig(Base):
    __tablename__ = "similarity_threshold_config"

    id = Column(Integer, primary_key=True, default=1)
    high_threshold = Column(Float, nullable=False)
    medium_threshold = Column(Float, nullable=False)
    low_threshold = Column(Float, nullable=False)
    updated_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
