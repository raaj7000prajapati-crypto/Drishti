from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.permissions import require_permission
from app.models.user import User
from pydantic import BaseModel
from datetime import datetime
from app.services.notification import (
    NotificationNotFound,
    get_user_notifications as list_user_notifications_service,
    mark_all_user_notifications_read,
    mark_user_notification_read,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    link: str | None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[NotificationResponse])
def get_user_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("notification.read"))
):
    """Retrieve in-app notifications for authenticated user."""
    return list_user_notifications_service(db, current_user.id)

@router.put("/{id}/read")
def mark_notification_read(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("notification.read"))
):
    """Mark a notification as read."""
    try:
        mark_user_notification_read(db, id, current_user.id)
    except NotificationNotFound as exc:
        raise HTTPException(
            status_code=404, detail="Notification not found"
        ) from exc
    return {"message": "Notification marked as read"}

@router.put("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("notification.read"))
):
    """Mark all notifications for authenticated user as read."""
    mark_all_user_notifications_read(db, current_user.id)
    return {"message": "All notifications marked as read"}
