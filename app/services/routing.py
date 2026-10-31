import re
from typing import Optional, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.bureau import Bureau
from app.models.user import User, Role
from app.models.complaint import Complaint, ComplaintStatus
from app.models.rules import RoutingRule
from app.core.logging import logger

def route_complaint(
    db: Session,
    category: str,
    subject: str,
    description: str
) -> Tuple[int, str]:
    """
    Intelligently route a complaint to the most appropriate AICTE Bureau
    based on Admin-configured keyword rules and categories.
    Defaults to 'Others' bureau if no rules match.
    Returns: (bureau_id, reason)
    """
    text_content = f"{subject} {description}".lower()
    norm_category = category.strip().lower() if category else ""

    rules = (
        db.query(RoutingRule)
        .filter(RoutingRule.is_active == True)
        .order_by(RoutingRule.priority.desc(), RoutingRule.id.asc())
        .all()
    )

    for rule in rules:
        # Check category match if rule specifies category
        cat_match = False
        if rule.category:
            if rule.category.strip().lower() == norm_category:
                cat_match = True
        else:
            cat_match = True  # Rule applies to any category

        # Check keywords match
        if rule.keywords:
            keywords = [k.strip().lower() for k in rule.keywords.split(",") if k.strip()]
            for kw in keywords:
                # Use word boundary search for accurate keyword detection
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, text_content):
                    logger.info(f"Routed to bureau ID {rule.target_bureau_id} via rule {rule.id} (matched keyword: '{kw}')")
                    return rule.target_bureau_id, f"Matched keyword rule: '{kw}'"

        # If rule specified category without keywords and category matched
        if cat_match and not rule.keywords and rule.category:
            logger.info(f"Routed to bureau ID {rule.target_bureau_id} via rule {rule.id} (matched category: '{rule.category}')")
            return rule.target_bureau_id, f"Matched category rule: '{rule.category}'"

    # Fallback to 'Others' bureau
    others_bureau = (
        db.query(Bureau)
        .filter(func.lower(Bureau.code) == "others")
        .first()
    )
    if not others_bureau:
        others_bureau = (
            db.query(Bureau)
            .filter(func.lower(Bureau.name).like("%other%"))
            .first()
        )
    if not others_bureau:
        others_bureau = db.query(Bureau).first()

    bureau_id = others_bureau.id if others_bureau else 1
    return bureau_id, "Default fallback to 'Others' bureau (no specific keywords matched)"

def assign_least_loaded_official(db: Session, bureau_id: int) -> Optional[int]:
    """
    Finds the active official in the specified bureau with the lowest count
    of active (non-closed) complaint cases.
    """
    officials = (
        db.query(User)
        .filter(
            User.role == Role.OFFICIAL,
            User.bureau_id == bureau_id,
            User.is_active == True
        )
        .all()
    )

    if not officials:
        return None

    # Calculate workload for each official
    best_official = None
    min_load = float("inf")

    for official in officials:
        active_cases_count = (
            db.query(func.count(Complaint.id))
            .filter(
                Complaint.assigned_official_id == official.id,
                Complaint.status != ComplaintStatus.CLOSED
            )
            .scalar()
        ) or 0

        if active_cases_count < min_load:
            min_load = active_cases_count
            best_official = official

    return best_official.id if best_official else None
