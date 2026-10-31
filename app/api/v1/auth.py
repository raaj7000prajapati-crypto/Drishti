import time
from collections import defaultdict
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    create_refresh_token, decode_token
)
from app.api.deps import get_current_user, get_client_ip
from app.models.user import User, Role
from app.models.bureau import Bureau
from app.schemas.user import UserCreate, UserLogin, Token, UserResponse
from app.services.audit import log_audit
from app.core.logging import logger

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory IP rate limiter for login protection
_login_attempts: Dict[str, List[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 10
WINDOW_SECONDS = 60

def check_login_rate_limit(ip: str):
    now = time.time()
    # Prune old timestamps
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < WINDOW_SECONDS]
    if len(_login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait 60 seconds before trying again."
        )
    _login_attempts[ip].append(now)

@router.post("/register", response_model=UserResponse)
def register(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Register a new citizen/student/institution complainant."""
    existing = db.query(User).filter(User.email == user_in.email.lower().strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )
    
    # Public registration only allows COMPLAINANT role
    role = Role.COMPLAINANT if user_in.role != Role.ADMIN else Role.COMPLAINANT

    new_user = User(
        email=user_in.email.lower().strip(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip(),
        phone=user_in.phone.strip() if user_in.phone else None,
        role=role,
        is_active=True
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
        after_state={"email": new_user.email, "role": new_user.role.value}
    )

    return new_user

@router.post("/login", response_model=Token)
def login(
    login_data: UserLogin,
    request: Request,
    db: Session = Depends(get_db)
):
    """Authenticate with email and password, returning JWT access and refresh tokens."""
    client_ip = get_client_ip(request)
    check_login_rate_limit(client_ip)

    email = login_data.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated"
        )

    token_data = {"sub": user.email, "role": user.role.value, "id": user.id}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)

    # Attach bureau name if applicable
    bureau_name = user.bureau.name if user.bureau else None
    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        bureau_id=user.bureau_id,
        is_active=user.is_active,
        created_at=user.created_at,
        bureau_name=bureau_name
    )

    log_audit(
        db=db,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        ip_address=client_ip
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_resp
    }

@router.post("/refresh")
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    """Issue a new access token using a valid refresh token."""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    user_email = payload.get("sub")
    user = db.query(User).filter(User.email == user_email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    new_token_data = {"sub": user.email, "role": user.role.value, "id": user.id}
    new_access_token = create_access_token(data=new_token_data)
    
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve currently authenticated user profile."""
    bureau_name = current_user.bureau.name if current_user.bureau else None
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        role=current_user.role,
        bureau_id=current_user.bureau_id,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        bureau_name=bureau_name
    )
