from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.audit import AuditLog
from app.models.bureau import Bureau
from app.models.complaint import Complaint, ComplaintStatus
from app.models.rules import RoutingRule, SLAConfig
from app.models.user import Role, User


def list_users(
    db: Session,
    role: Optional[str] = None,
    bureau_id: Optional[int] = None,
) -> list[User]:
    query = db.query(User).options(joinedload(User.bureau))
    if role and role != "All":
        query = query.filter(User.role == role)
    if bureau_id:
        query = query.filter(User.bureau_id == bureau_id)
    return query.order_by(User.id.asc()).all()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return (
        db.query(User)
        .options(joinedload(User.bureau))
        .filter(User.id == user_id)
        .first()
    )


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def list_bureaus_with_counts(
    db: Session,
    actor: User,
) -> list[tuple[Bureau, int, int]]:
    official_count = (
        db.query(func.count(User.id))
        .filter(User.bureau_id == Bureau.id, User.is_active.is_(True))
        .correlate(Bureau)
        .scalar_subquery()
    )
    active_complaint_count = (
        db.query(func.count(Complaint.id))
        .filter(
            Complaint.bureau_id == Bureau.id,
            Complaint.status != ComplaintStatus.CLOSED,
        )
        .correlate(Bureau)
        .scalar_subquery()
    )
    query = db.query(Bureau, official_count, active_complaint_count)
    if actor.role == Role.OFFICIAL:
        if actor.bureau_id is None:
            return []
        query = query.filter(Bureau.id == actor.bureau_id)
    return query.order_by(Bureau.id.asc()).all()


def list_routing_rules(db: Session) -> list[RoutingRule]:
    return (
        db.query(RoutingRule)
        .options(joinedload(RoutingRule.target_bureau))
        .order_by(RoutingRule.priority.desc(), RoutingRule.id.asc())
        .all()
    )


def get_routing_rule(db: Session, rule_id: int) -> RoutingRule | None:
    return db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()


def list_sla_configs(db: Session) -> list[SLAConfig]:
    return db.query(SLAConfig).order_by(SLAConfig.id.asc()).all()


def get_sla_config(db: Session, priority: str) -> SLAConfig | None:
    return (
        db.query(SLAConfig)
        .filter(SLAConfig.priority.ilike(priority))
        .first()
    )


def list_audit_logs(
    db: Session,
    *,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    actor_email: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
) -> list[AuditLog]:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if actor_email:
        query = query.filter(AuditLog.actor_email.ilike(f"%{actor_email}%"))
    return (
        query.order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
