from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.bureau import Bureau
from app.models.rules import RoutingRule, SLAConfig
from app.models.user import Role, User
from app.repositories.admin import (
    get_routing_rule,
    get_sla_config,
    get_user_by_email,
    get_user_by_id,
)
from app.schemas.admin import BureauCreate, RoutingRuleCreate, SLAConfigUpdate
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit import log_audit


class AdminConflict(Exception):
    pass


class AdminResourceNotFound(Exception):
    pass


def create_user(
    db: Session,
    data: UserCreate,
    actor: User,
    ip_address: Optional[str],
) -> User:
    email = data.email.lower().strip()
    if get_user_by_email(db, email):
        raise AdminConflict("User with this email already exists.")
    user = User(
        email=email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name.strip(),
        phone=data.phone.strip() if data.phone else None,
        role=data.role,
        bureau_id=data.bureau_id if data.role == Role.OFFICIAL else None,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_audit(
        db,
        action="USER_PROVISIONED_BY_ADMIN",
        entity_type="User",
        entity_id=str(user.id),
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
        after_state={
            "email": user.email,
            "role": user.role.value,
            "bureau_id": user.bureau_id,
        },
    )
    return user


def update_user(
    db: Session,
    user_id: int,
    data: UserUpdate,
    actor: User,
    ip_address: Optional[str],
) -> User:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise AdminResourceNotFound("User not found.")
    before_state = {
        "role": user.role.value,
        "is_active": user.is_active,
        "bureau_id": user.bureau_id,
    }
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.phone is not None:
        user.phone = data.phone
    if data.role is not None:
        user.role = data.role
    if data.bureau_id is not None:
        user.bureau_id = data.bureau_id
    if data.is_active is not None:
        user.is_active = data.is_active
    db.commit()
    db.refresh(user)
    log_audit(
        db,
        action="USER_UPDATED_BY_ADMIN",
        entity_type="User",
        entity_id=str(user.id),
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
        before_state=before_state,
        after_state={
            "role": user.role.value,
            "is_active": user.is_active,
            "bureau_id": user.bureau_id,
        },
    )
    return user


def create_bureau(
    db: Session,
    data: BureauCreate,
    actor: User,
    ip_address: Optional[str],
) -> Bureau:
    bureau = Bureau(
        name=data.name.strip(),
        code=data.code.strip().upper(),
        description=data.description,
        head_email=data.head_email,
    )
    db.add(bureau)
    db.commit()
    db.refresh(bureau)
    log_audit(
        db,
        action="BUREAU_CREATED",
        entity_type="Bureau",
        entity_id=str(bureau.id),
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
        after_state={"name": bureau.name, "code": bureau.code},
    )
    return bureau


def create_routing_rule(
    db: Session,
    data: RoutingRuleCreate,
    actor: User,
    ip_address: Optional[str],
) -> RoutingRule:
    rule = RoutingRule(
        category=data.category.strip() if data.category else None,
        keywords=data.keywords.strip().lower(),
        target_bureau_id=data.target_bureau_id,
        priority=data.priority,
        is_active=data.is_active,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    log_audit(
        db,
        action="ROUTING_RULE_CREATED",
        entity_type="RoutingRule",
        entity_id=str(rule.id),
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
        after_state={
            "keywords": rule.keywords,
            "target_bureau_id": rule.target_bureau_id,
        },
    )
    return rule


def delete_routing_rule(
    db: Session,
    rule_id: int,
    actor: User,
    ip_address: Optional[str],
) -> None:
    rule = get_routing_rule(db, rule_id)
    if rule is None:
        raise AdminResourceNotFound("Rule not found.")
    db.delete(rule)
    db.commit()
    log_audit(
        db,
        action="ROUTING_RULE_DELETED",
        entity_type="RoutingRule",
        entity_id=str(rule_id),
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
    )


def update_sla_config(
    db: Session,
    priority: str,
    data: SLAConfigUpdate,
    actor: User,
    ip_address: Optional[str],
) -> SLAConfig:
    config = get_sla_config(db, priority)
    if config is None:
        config = SLAConfig(
            priority=priority.capitalize(),
            max_hours=data.max_hours,
            escalation_level=data.escalation_level,
        )
        db.add(config)
    else:
        config.max_hours = data.max_hours
        if data.escalation_level:
            config.escalation_level = data.escalation_level
    db.commit()
    db.refresh(config)
    log_audit(
        db,
        action="SLA_CONFIG_UPDATED",
        entity_type="SLAConfig",
        entity_id=str(config.id),
        actor_id=actor.id,
        actor_email=actor.email,
        ip_address=ip_address,
        after_state={"priority": config.priority, "max_hours": config.max_hours},
    )
    return config
