import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_refresh_token as encode_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models.user import RefreshToken, Role, User
from app.repositories.authentication import (
    get_refresh_token_by_jti,
    get_user_by_email,
)
from app.schemas.user import UserCreate
from app.services.audit import log_audit


class DuplicateUserError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InactiveUserError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


def register_complainant(
    db: Session, data: UserCreate, ip_address: str | None
) -> User:
    email = data.email.lower().strip()
    if get_user_by_email(db, email):
        raise DuplicateUserError("A user with this email address already exists.")

    user = User(
        email=email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name.strip(),
        phone=data.phone.strip() if data.phone else None,
        role=Role.COMPLAINANT,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(
        db=db,
        action="USER_REGISTER",
        entity_type="User",
        entity_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        ip_address=ip_address,
        after_state={"email": user.email, "role": user.role.value},
    )
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError
    if not user.is_active:
        raise InactiveUserError
    return user


def create_refresh_session(db: Session, user: User, ip_address: str) -> str:
    token = _new_refresh_token(db, user)
    log_audit(
        db=db,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        ip_address=ip_address,
    )
    return token


def rotate_refresh_session(
    db: Session, jti: str, email: str
) -> tuple[User, str]:
    token_record = get_refresh_token_by_jti(db, jti)
    user = get_user_by_email(db, email)
    if (
        not token_record
        or token_record.revoked_at is not None
        or not user
        or not user.is_active
        or token_record.user_id != user.id
    ):
        raise InvalidRefreshTokenError

    token_record.revoked_at = datetime.now(timezone.utc)
    new_token = _new_refresh_token(db, user)
    db.commit()
    return user, new_token


def revoke_refresh_session(db: Session, jti: str) -> None:
    token_record = get_refresh_token_by_jti(db, jti)
    if token_record and token_record.revoked_at is None:
        token_record.revoked_at = datetime.now(timezone.utc)
        db.commit()


def _new_refresh_token(db: Session, user: User) -> str:
    jti = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    token = encode_refresh_token(
        data={"sub": user.email, "role": user.role.value, "id": user.id, "jti": jti},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    return token
