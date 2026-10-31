from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_client_ip
from app.core.permissions import require_permission
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.admin import (
    BureauCreate, BureauResponse, RoutingRuleCreate,
    RoutingRuleResponse, SLAConfigUpdate,
    SLAConfigResponse, AuditLogResponse, ReassignComplaintRequest,
    SimilarityThresholdsUpdate, SimilarityThresholdsResponse,
)
from app.repositories.admin import (
    list_audit_logs as query_audit_logs,
    list_bureaus_with_counts,
    list_routing_rules as query_routing_rules,
    list_sla_configs as query_sla_configs,
    list_users as query_users,
)
from app.services.administration import (
    AdminConflict,
    AdminResourceNotFound,
    create_bureau as create_bureau_service,
    create_routing_rule,
    create_user as create_user_service,
    delete_routing_rule,
    update_sla_config as update_sla_config_service,
    update_user as update_user_service,
)
from app.services.cases import (
    CaseNotFoundError,
    CaseWorkflowConflict,
    InvalidCaseTransition,
    reassign_case,
)
from app.services.similarity import (
    get_similarity_thresholds,
    update_similarity_thresholds,
)

router = APIRouter(prefix="/admin", tags=["Admin Operations"])

admin_only = require_permission("admin.manage")


@router.get(
    "/similarity-thresholds", response_model=SimilarityThresholdsResponse
)
def read_similarity_thresholds(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    return get_similarity_thresholds(db)


@router.put(
    "/similarity-thresholds", response_model=SimilarityThresholdsResponse
)
def change_similarity_thresholds(
    thresholds: SimilarityThresholdsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    return update_similarity_thresholds(
        db,
        high_threshold=thresholds.high_threshold,
        medium_threshold=thresholds.medium_threshold,
        low_threshold=thresholds.low_threshold,
        actor=current_user,
        ip_address=get_client_ip(request),
    )

# --- Users Management ---
@router.get("/users", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = None,
    bureau_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """List all registered platform users with filters."""
    users = query_users(db, role, bureau_id)
    return [
        UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            phone=u.phone,
            role=u.role,
            bureau_id=u.bureau_id,
            is_active=u.is_active,
            created_at=u.created_at,
            bureau_name=u.bureau.name if u.bureau else None
        )
        for u in users
    ]

@router.post("/users", response_model=UserResponse)
def create_user(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Admin provisions an official or administrator account."""
    try:
        new_user = create_user_service(
            db, user_in, current_user, get_client_ip(request)
        )
    except AdminConflict as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    try:
        user = update_user_service(
            db, id, user_update, current_user, get_client_ip(request)
        )
    except AdminResourceNotFound as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc

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
    bureau_rows = list_bureaus_with_counts(db, current_user)
    return [
        BureauResponse(
            id=b.id,
            name=b.name,
            code=b.code,
            description=b.description,
            head_email=b.head_email,
            is_active=b.is_active,
            created_at=b.created_at,
            official_count=official_count,
            active_complaints_count=active_complaint_count,
        )
        for b, official_count, active_complaint_count in bureau_rows
    ]

@router.post("/bureaus", response_model=BureauResponse)
def create_bureau(
    bureau_in: BureauCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Create a new bureau or cell."""
    bureau = create_bureau_service(
        db, bureau_in, current_user, get_client_ip(request)
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
    rules = query_routing_rules(db)
    return [
        RoutingRuleResponse(
            id=r.id,
            category=r.category,
            keywords=r.keywords,
            target_bureau_id=r.target_bureau_id,
            target_bureau_name=r.target_bureau.name if r.target_bureau else "Unknown",
            priority=r.priority,
            is_active=r.is_active,
            created_at=r.created_at
        )
        for r in rules
    ]

@router.post("/rules", response_model=RoutingRuleResponse)
def create_rule(
    rule_in: RoutingRuleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Create a smart routing keyword/category rule."""
    rule = create_routing_rule(
        db, rule_in, current_user, get_client_ip(request)
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
    try:
        delete_routing_rule(db, id, current_user, get_client_ip(request))
    except AdminResourceNotFound as exc:
        raise HTTPException(status_code=404, detail="Rule not found") from exc
    return {"message": "Rule deleted"}

# --- SLA Configurations ---
@router.get("/sla", response_model=List[SLAConfigResponse])
def get_sla_configs(db: Session = Depends(get_db), current_user: User = Depends(admin_only)):
    """List SLA configurations for each priority tier."""
    return query_sla_configs(db)

@router.put("/sla/{priority}", response_model=SLAConfigResponse)
def update_sla_config(
    priority: str,
    sla_in: SLAConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only)
):
    """Update max hours and escalation levels for a given priority tier."""
    return update_sla_config_service(
        db, priority, sla_in, current_user, get_client_ip(request)
    )

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
    try:
        reassign_case(
            db,
            id,
            reassign_in.bureau_id,
            reassign_in.official_id,
            reassign_in.reason,
            current_user,
            get_client_ip(request),
        )
    except CaseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Complaint not found") from exc
    except (CaseWorkflowConflict, InvalidCaseTransition) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

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
    return query_audit_logs(
        db,
        action=action,
        entity_type=entity_type,
        actor_email=actor_email,
        skip=skip,
        limit=limit,
    )


@router.get("/audit-logs/verify")
def verify_audit_log_chain(
    db: Session = Depends(get_db),
    current_user: User = Depends(admin_only),
):
    """Verify every audit entry and return the first invalid entry, if any."""
    from app.services.audit import verify_audit_chain

    return verify_audit_chain(db)
