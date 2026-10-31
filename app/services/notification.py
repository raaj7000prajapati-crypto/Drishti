import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.logging import logger
from app.models.notification import Notification
from app.repositories.notifications import (
    get_notification_for_user,
    list_notifications_for_user,
    mark_notifications_read_for_user,
)


class NotificationNotFound(Exception):
    pass

def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
    link: Optional[str] = None
) -> Notification:
    """Create in-app notification record."""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        link=link,
        is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def get_user_notifications(db: Session, user_id: int) -> list[Notification]:
    return list_notifications_for_user(db, user_id)


def mark_user_notification_read(
    db: Session, notification_id: int, user_id: int
) -> None:
    notification = get_notification_for_user(db, notification_id, user_id)
    if notification is None:
        raise NotificationNotFound
    notification.is_read = True
    db.commit()


def mark_all_user_notifications_read(db: Session, user_id: int) -> None:
    mark_notifications_read_for_user(db, user_id)
    db.commit()


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """Send transactional email via SMTP (e.g., MailHog dev server or production SMTP)."""
    if not settings.ENABLE_EMAIL or not to_email:
        return False
        
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
        msg["To"] = to_email

        if text_content:
            msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, [to_email], msg.as_string())
            
        logger.info(f"Email sent successfully to {to_email} with subject '{subject}'")
        return True
    except Exception as e:
        logger.warning(f"Could not send email to {to_email} via {settings.SMTP_HOST}:{settings.SMTP_PORT} - {e}")
        return False
