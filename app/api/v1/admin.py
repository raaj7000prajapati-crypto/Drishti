from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.api.deps import get_client_ip
from app.core.permissions import require_permission
from app.core.security import get_password_hash
from app.models.user import User, Role
from app.models.bureau import Bureau
from app.models.complaint import Complaint, ComplaintEvent, ComplaintStatus
from app.models.rules import RoutingRule, SLAConfig
from app.models.audit import AuditLog
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.admin import (
    BureauCreate, BureauResponse, RoutingRuleCreate,
    RoutingRuleUpdate, RoutingRuleResponse, SLAConfigUpdate,
    SLAConfigResponse, AuditLogResponse, ReassignComplaintRequest
)
from app.services.notification import create_notification
from app.services.audit import log_audit

router = APIRouter(prefix="/admin", tags=["Admin Operations"])

admin_only = require_permission("admin.manage")

# --- Users Management ---
@router.get("/users", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = None,
    bureau_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """List all registered platform users with filters."""
    query = db.query(User)
    if role and role != "All":
        query = query.filter(User.role == role)
    if bureau_id:
        query = query.filter(User.bureau_id == bureau_id)
    
    users = query.order_by(User.id.asc()).all()
    resp = []
    for u in users:
        resp.append(UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            phone=u.phone,
            role=u.role,
            bureau_id=u.bureau_id,
            is_active=u.is_active,
            created_at=u.created_at,
            bureau_name=u.bureau.name if u.bureau else None
        ))
    return resp

@router.post("/users", response_model=UserResponse)
def create_user(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Admin provisions an official or administrator account."""
    existing = db.query(User).filter(User.email == user_in.email.lower().strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    new_user = User(
        email=user_in.email.lower().strip(),
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name.strip(),
        phone=user_in.phone.strip() if user_in.phone else None,
        role=user_in.role,
        bureau_id=user_in.bureau_id if user_in.role == Role.OFFICIAL else None,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(
        db=db,
        action="USER_PROVISIONED_BY_ADMIN",
        entity_type="User",
        entity_id=str(new_user.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        after_state={"email": new_user.email, "role": new_user.role.value, "bureau_id": new_user.bureau_id}
    )

    bureau_name = new_user.bureau.name if new_user.bureau else None
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        full_name=new_user.full_name,
        phone=new_user.phone,
        role=new_user.role,
        bureau_id=new_user.bureau_id,
        is_active=new_user.is_active,
        created_at=new_user.created_at,
        bureau_name=bureau_name
    )

@router.put("/users/{id}", response_model=UserResponse)
def update_user(
    id: int,
    user_update: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Update user role, status or bureau allocation."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    before_state = {"role": user.role.value, "is_active": user.is_active, "bureau_id": user.bureau_id}

    if user_update.full_name is not None:
        user.full_name = user_update.full_name
    if user_update.phone is not None:
        user.phone = user_update.phone
    if user_update.role is not None:
        user.role = user_update.role
    if user_update.bureau_id is not None:
        user.bureau_id = user_update.bureau_id
    if user_update.is_active is not None:
        user.is_active = user_update.is_active

    db.commit()
    db.refresh(user)

    log_audit(
        db=db,
        action="USER_UPDATED_BY_ADMIN",
        entity_type="User",
        entity_id=str(user.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        before_state=before_state,
        after_state={"role": user.role.value, "is_active": user.is_active, "bureau_id": user.bureau_id}
    )

    bureau_name = user.bureau.name if user.bureau else None
    return UserResponse(
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

# --- Bureau Management ---
@router.get("/bureaus", response_model=List[BureauResponse])
def list_bureaus(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("bureau.read")),
):
    """List all AICTE bureaus and cells with workload metrics."""
    bureau_query = db.query(Bureau)
    if current_user.role == Role.OFFICIAL:
        if current_user.bureau_id is None:
            return []
        bureau_query = bureau_query.filter(Bureau.id == current_user.bureau_id)
    bureaus = bureau_query.order_by(Bureau.id.asc()).all()
    resp = []
    for b in bureaus:
        official_count = db.query(func.count(User.id)).filter(User.bureau_id == b.id, User.is_active == True).scalar() or 0
        active_complaints = db.query(func.count(Complaint.id)).filter(Complaint.bureau_id == b.id, Complaint.status != ComplaintStatus.CLOSED).scalar() or 0
        resp.append(BureauResponse(
            id=b.id,
            name=b.name,
            code=b.code,
            description=b.description,
            head_email=b.head_email,
            is_active=b.is_active,
            created_at=b.created_at,
            official_count=official_count,
            active_complaints_count=active_complaints
        ))
    return resp

@router.post("/bureaus", response_model=BureauResponse)
def create_bureau(
    bureau_in: BureauCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Create a new bureau or cell."""
    bureau = Bureau(
        name=bureau_in.name.strip(),
        code=bureau_in.code.strip().upper(),
        description=bureau_in.description,
        head_email=bureau_in.head_email
    )
    db.add(bureau)
    db.commit()
    db.refresh(bureau)

    log_audit(
        db=db,
        action="BUREAU_CREATED",
        entity_type="Bureau",
        entity_id=str(bureau.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        after_state={"name": bureau.name, "code": bureau.code}
    )

    return BureauResponse(
        id=bureau.id,
        name=bureau.name,
        code=bureau.code,
        description=bureau.description,
        head_email=bureau.head_email,
        is_active=bureau.is_active,
        created_at=bureau.created_at,
        official_count=0,
        active_complaints_count=0
    )

# --- Routing Rules ---
@router.get("/rules", response_model=List[RoutingRuleResponse])
def list_rules(db: Session = Depends(get_db), current_user: User = Depends(admin_only)):
    """List keyword and category routing rules."""
    rules = db.query(RoutingRule).order_by(RoutingRule.priority.desc(), RoutingRule.id.asc()).all()
    resp = []
    for r in rules:
        resp.append(RoutingRuleResponse(
            id=r.id,
            category=r.category,
            keywords=r.keywords,
            target_bureau_id=r.target_bureau_id,
            target_bureau_name=r.target_bureau.name if r.target_bureau else "Unknown",
            priority=r.priority,
            is_active=r.is_active,
            created_at=r.created_at
        ))
    return resp

@router.post("/rules", response_model=RoutingRuleResponse)
def create_rule(
    rule_in: RoutingRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Create a smart routing keyword/category rule."""
    rule = RoutingRule(
        category=rule_in.category.strip() if rule_in.category else None,
        keywords=rule_in.keywords.strip().lower(),
        target_bureau_id=rule_in.target_bureau_id,
        priority=rule_in.priority,
        is_active=rule_in.is_active
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    log_audit(
        db=db,
        action="ROUTING_RULE_CREATED",
        entity_type="RoutingRule",
        entity_id=str(rule.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        after_state={"keywords": rule.keywords, "target_bureau_id": rule.target_bureau_id}
    )

    return RoutingRuleResponse(
        id=rule.id,
        category=rule.category,
        keywords=rule.keywords,
        target_bureau_id=rule.target_bureau_id,
        target_bureau_name=rule.target_bureau.name if rule.target_bureau else "Unknown",
        priority=rule.priority,
        is_active=rule.is_active,
        created_at=rule.created_at
    )

@router.delete("/rules/{id}")
def delete_rule(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    rule = db.query(RoutingRule).filter(RoutingRule.id == id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(rule)
    db.commit()

    log_audit(
        db=db,
        action="ROUTING_RULE_DELETED",
        entity_type="RoutingRule",
        entity_id=str(id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request)
    )
    return {"message": "Rule deleted"}

# --- SLA Configurations ---
@router.get("/sla", response_model=List[SLAConfigResponse])
def get_sla_configs(db: Session = Depends(get_db), current_user: User = Depends(admin_only)):
    """List SLA configurations for each priority tier."""
    configs = db.query(SLAConfig).order_by(SLAConfig.id.asc()).all()
    return configs

@router.put("/sla/{priority}", response_model=SLAConfigResponse)
def update_sla_config(
    priority: str,
    sla_in: SLAConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Update max hours and escalation levels for a given priority tier."""
    config = db.query(SLAConfig).filter(SLAConfig.priority.ilike(priority)).first()
    if not config:
        config = SLAConfig(priority=priority.capitalize(), max_hours=sla_in.max_hours, escalation_level=sla_in.escalation_level)
        db.add(config)
    else:
        config.max_hours = sla_in.max_hours
        if sla_in.escalation_level:
            config.escalation_level = sla_in.escalation_level

    db.commit()
    db.refresh(config)

    log_audit(
        db=db,
        action="SLA_CONFIG_UPDATED",
        entity_type="SLAConfig",
        entity_id=str(config.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        after_state={"priority": config.priority, "max_hours": config.max_hours}
    )

    return config

# --- Case Reassignment ---
@router.post("/complaints/{id}/reassign")
def reassign_complaint(
    id: int,
    reassign_in: ReassignComplaintRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Admin reassigns complaint to a different bureau and/or official."""
    complaint = db.query(Complaint).filter(Complaint.id == id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    target_bureau = db.query(Bureau).filter(Bureau.id == reassign_in.bureau_id).first()
    if not target_bureau:
        raise HTTPException(status_code=400, detail="Target bureau not found")

    before_state = {
        "bureau_id": complaint.bureau_id,
        "official_id": complaint.assigned_official_id
    }

    complaint.bureau_id = target_bureau.id
    if reassign_in.official_id:
        complaint.assigned_official_id = reassign_in.official_id
    complaint.status = ComplaintStatus.ASSIGNED

    # Timeline event
    event = ComplaintEvent(
        complaint_id=complaint.id,
        actor_id=current_user.id,
        event_type="REASSIGNED",
        title=f"Reassigned to {target_bureau.name}",
        description=f"Admin {current_user.full_name} manually reassigned case. Reason: {reassign_in.reason or 'Administrative re-allocation'}."
    )
    db.add(event)
    db.commit()

    # Notify new official if assigned
    if complaint.assigned_official_id:
        create_notification(
            db=db,
            user_id=complaint.assigned_official_id,
            title=f"Case Reassigned to You: {complaint.receipt_id}",
            message=f"Administrator reassigned complaint {complaint.receipt_id} to your bureau.",
            link=f"/cases/{complaint.id}"
        )

    log_audit(
        db=db,
        action="CASE_REASSIGNED_BY_ADMIN",
        entity_type="Complaint",
        entity_id=str(complaint.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        ip_address=get_client_ip(request),
        before_state=before_state,
        after_state={"bureau_id": complaint.bureau_id, "official_id": complaint.assigned_official_id, "reason": reassign_in.reason}
    )

    return {"message": "Complaint reassigned successfully"}

# --- Append-Only Audit Log Viewer ---
@router.get("/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    actor_email: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Read-only view of the immutable audit trail logs."""
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if actor_email:
        query = query.filter(AuditLog.actor_email.ilike(f"%{actor_email}%"))

    logs = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    return logs


@router.get("/audit-logs/verify")
def verify_audit_log_chain(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    """Verify every audit entry and return the first invalid entry, if any."""
    from app.services.audit import verify_audit_chain

    return verify_audit_chain(db)
