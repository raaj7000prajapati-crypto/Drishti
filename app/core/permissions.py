from collections.abc import Collection

from fastapi import HTTPException, status

from app.models.complaint import Complaint
from app.models.user import Role, User

ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.COMPLAINANT: frozenset({
        "complaint.create",
        "complaint.read",
        "complaint.duplicate_check",
        "complaint.respond_info",
        "complaint.feedback",
        "notification.read",
    }),
    Role.OFFICIAL: frozenset({
        "complaint.read",
        "complaint.manage",
        "complaint.duplicate_check",
        "notification.read",
        "analytics.read",
        "report.export",
        "bureau.read",
    }),
    Role.ADMIN: frozenset({"*"}),
}


def has_permission(role: Role, permission: str) -> bool:
    permissions = ROLE_PERMISSIONS.get(role, frozenset())
    return "*" in permissions or permission in permissions


def require_permission(permission: str):
    from app.api.deps import get_current_user
    from fastapi import Depends

    def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted",
            )
        return current_user

    return permission_checker


def ensure_complaint_access(user: User, complaint: Complaint) -> None:
    if user.role == Role.ADMIN:
        return
    if user.role == Role.COMPLAINANT and complaint.complainant_id == user.id:
        return
    if (
        user.role == Role.OFFICIAL
        and user.bureau_id is not None
        and complaint.bureau_id == user.bureau_id
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied to this grievance record",
    )


def require_all_complaint_access(user: User, complaints: Collection[Complaint]) -> None:
    for complaint in complaints:
        ensure_complaint_access(user, complaint)


def validate_production_security() -> None:
    from app.core.config import INSECURE_SECRET_KEY, settings

    if settings.APP_ENV.strip().lower() in {"prod", "production"} and (
        settings.SECRET_KEY == INSECURE_SECRET_KEY or len(settings.SECRET_KEY) < 32
    ):
        raise RuntimeError("Production startup requires a unique SECRET_KEY of at least 32 characters.")
