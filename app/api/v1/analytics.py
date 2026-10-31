from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.analytics import DashboardStatsResponse
from app.services.analytics import build_dashboard_analytics
from app.services.dashboard_cache import DashboardStatsCache

router = APIRouter(prefix="/analytics", tags=["Analytics & Metrics"])
dashboard_cache = DashboardStatsCache(settings.DASHBOARD_CACHE_TTL_SECONDS)


@router.get("/dashboard", response_model=DashboardStatsResponse)
def get_dashboard_analytics(
    bureau_id: Optional[int] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    date_range_days: int = Query(180, ge=7, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics.read")),
):
    cache_key = (
        current_user.role.value,
        current_user.id,
        current_user.bureau_id,
        bureau_id,
        priority,
        status,
        date_range_days,
    )
    return dashboard_cache.get_or_compute(
        cache_key,
        lambda: build_dashboard_analytics(
            db,
            bureau_id=bureau_id,
            priority=priority,
            status=status,
            date_range_days=date_range_days,
            actor=current_user,
        ),
    )
