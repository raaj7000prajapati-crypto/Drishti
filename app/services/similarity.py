from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.similarity import SimilarityThresholdConfig
from app.models.user import User
from app.repositories.admin import get_similarity_threshold_config
from app.services.audit import log_audit


def get_similarity_thresholds(db: Session) -> dict[str, float | datetime | None]:
    config = get_similarity_threshold_config(db)
    if config is None:
        return {
            "high_threshold": settings.SIMILARITY_HIGH_THRESHOLD,
            "medium_threshold": settings.SIMILARITY_MEDIUM_THRESHOLD,
            "low_threshold": settings.SIMILARITY_LOW_THRESHOLD,
            "updated_at": None,
        }
    return {
        "high_threshold": config.high_threshold,
        "medium_threshold": config.medium_threshold,
        "low_threshold": config.low_threshold,
        "updated_at": config.updated_at,
    }


def update_similarity_thresholds(
    db: Session,
    *,
    high_threshold: float,
    medium_threshold: float,
    low_threshold: float,
    actor: User,
    ip_address: str | None = None,
) -> SimilarityThresholdConfig:
    config = get_similarity_threshold_config(db)
    before = (
        {
            "high_threshold": config.high_threshold,
            "medium_threshold": config.medium_threshold,
            "low_threshold": config.low_threshold,
        }
        if config
        else get_similarity_thresholds(db)
    )
    if config is None:
        config = SimilarityThresholdConfig(id=1)
        db.add(config)
    config.high_threshold = high_threshold
    config.medium_threshold = medium_threshold
    config.low_threshold = low_threshold
    config.updated_by_id = actor.id
    config.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(config)

    log_audit(
        db,
        action="SIMILARITY_THRESHOLDS_UPDATED",
        entity_type="SimilarityThresholdConfig",
        entity_id="1",
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
        before_state=before,
        after_state={
            "high_threshold": high_threshold,
            "medium_threshold": medium_threshold,
            "low_threshold": low_threshold,
        },
    )
    return config
