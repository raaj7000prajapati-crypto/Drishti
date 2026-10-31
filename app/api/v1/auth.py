import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Deque

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import RefreshToken, Role, User
from app.schemas.user import Token, UserCreate, UserLogin, UserResponse
from app.services.audit import log_audit

router = APIRouter(prefix="/auth", tags=["Authentication"])

_attempts_by_ip: dict[str, Deque[float]] = defaultdict(deque)
_lockouts: dict[str, tuple[int, float]] = {}
_login_state_lock = Lock()
RATE_LIMIT_ATTEMPTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60


def _lockout_key(email: str) -> str:
    return email


def check_login_rate_limit(client_ip: str, email: str) -> None:
    now = time.monotonic()
    key = _lockout_key(email)
    with _login_state_lock:
        failures, locked_until = _lockouts.get(key, (0, 0.0))
        if locked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later.",
            )
        if locked_until:
            _lockouts.pop(key, None)

        attempts = _attempts_by_ip[client_ip]
        while attempts and now - attempts[0] >= RATE_LIMIT_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= RATE_LIMIT_ATTEMPTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Please wait before trying again.",
            )
        attempts.append(now)


def record_login_failure(email: str, client_ip: str) -> None:
    key = _lockout_key(email)
    now = time.monotonic()
    with _login_state_lock:
        failures, _ = _lockouts.get(key, (0, 0.0))
        failures += 1
        locked_until = 0.0
        if failures >= settings.LOGIN_FAILURE_LIMIT:
            locked_until = now + settings.LOGIN_LOCKOUT_MINUTES * 60
            logger.warning(
                "Login identity temporarily locked after repeated failures",
                extra={"client_ip": client_ip, "email": email},
            )
        _lockouts[key] = (failures, locked_until)


def clear_login_failures(email: str) -> None:
    with _login_state_lock:
        _lockouts.pop(_lockout_key(email), None)


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="drishti_refresh",
        value=token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/api/v1/auth",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="drishti_refresh",
        path="/api/v1/auth",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )


def _new_refresh_token(db: Session, user: User) -> str:
    jti = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token = create_refresh_token(
        data={"sub": user.email, "role": user.role.value, "id": user.id, "jti": jti},
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires_at))
    return token


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        bureau_id=user.bureau_id,
        is_active=user.is_active,
        created_at=user.created_at,
        bureau_name=user.bureau.name if user.bureau else None,
    )


@router.post("/register", response_model=UserResponse)
def register(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new citizen/student/institution complainant."""
    email = user_in.email.lower().strip()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists",
        )

    new_user = User(
        email=email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip(),
        phone=user_in.phone.strip() if user_in.phone else None,
        role=Role.COMPLAINANT,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(
        db=db,
        action="USER_REGISTER",
        entity_type="User",
        entity_id=str(new_user.id),
        actor_id=new_user.id,
        actor_email=new_user.email,
        ip_address=get_client_ip(request),
        after_state={"email": new_user.email, "role": new_user.role.value},
    )
    return new_user


@router.post("/login", response_model=Token)
def login(
    login_data: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate and issue a short-lived access token and refresh cookie."""
    client_ip = get_client_ip(request)
    email = login_data.email.lower().strip()
    check_login_rate_limit(client_ip, email)
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        record_login_failure(email, client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )

    clear_login_failures(email)
    token_data = {"sub": user.email, "role": user.role.value, "id": user.id}
    access_token = create_access_token(data=token_data)
    refresh_token = _new_refresh_token(db, user)
    db.commit()
    set_refresh_cookie(response, refresh_token)

    log_audit(
        db=db,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        ip_address=client_ip,
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _user_response(user),
    }


@router.post("/refresh")
def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Rotate the refresh cookie and issue a new access token."""
    token = request.cookies.get("drishti_refresh")
    payload = decode_token(token) if token else {}
    jti = payload.get("jti")
    if payload.get("type") != "refresh" or not jti:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    token_record = db.query(RefreshToken).filter(RefreshToken.jti == jti).first()
    user = db.query(User).filter(User.email == payload.get("sub")).first()
    if (
        not token_record
        or token_record.revoked_at is not None
        or not user
        or not user.is_active
        or token_record.user_id != user.id
    ):
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token",
        )

    token_record.revoked_at = datetime.now(timezone.utc)
    new_refresh_token = _new_refresh_token(db, user)
    new_access_token = create_access_token(
        data={"sub": user.email, "role": user.role.value, "id": user.id}
    )
    db.commit()
    set_refresh_cookie(response, new_refresh_token)
    return {"access_token": new_access_token, "token_type": "bearer"}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Revoke the refresh token, when present, and clear the browser cookie."""
    token = request.cookies.get("drishti_refresh")
    payload = decode_token(token, verify_exp=False) if token else {}
    jti = payload.get("jti")
    if payload.get("type") == "refresh" and jti:
        token_record = db.query(RefreshToken).filter(RefreshToken.jti == jti).first()
        if token_record and token_record.revoked_at is None:
            token_record.revoked_at = datetime.now(timezone.utc)
            db.commit()
    clear_refresh_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve currently authenticated user profile."""
    return _user_response(current_user)
