from typing import Optional

from sqlalchemy.orm import Session

from app.core.permissions import require_all_complaint_access
from app.models.complaint import CaseLink, ComplaintEvent
from app.models.user import User
from app.repositories.cases import get_case_link_for_update
from app.services.cases import CaseWorkflowConflict
from app.services.correlation import decide_case_link


class CaseLinkNotFound(Exception):
    pass


class LinkedComplaintNotFound(Exception):
    pass


def decide_case_link_workflow(
    db: Session,
    link_id: int,
    decision: str,
    actor: User,
    ip_address: Optional[str],
) -> CaseLink:
    link = get_case_link_for_update(db, link_id)
    if link is None:
        raise CaseLinkNotFound(f"Case link {link_id} not found.")
    if link.source_complaint is None or link.target_complaint is None:
        raise LinkedComplaintNotFound("A linked complaint record no longer exists.")
    require_all_complaint_access(
        actor,
        [link.source_complaint, link.target_complaint],
    )
    if link.status != "SUGGESTED":
        raise CaseWorkflowConflict("This case link has already been decided.")

    decided_link = decide_case_link(
        db=db,
        link_id=link.id,
        decision=decision,
        deciding_user=actor,
        ip_address=ip_address,
    )
    db.add_all(
        [
            ComplaintEvent(
                complaint_id=decided_link.source_complaint_id,
                actor_id=actor.id,
                event_type=f"LINK_{decision}",
                title=f"AI Case Correlation {decision.capitalize()}",
                description=(
                    f"Official {actor.full_name} {decision.lower()} a related case link "
                    f"(Match score: {int(decided_link.similarity_score * 100)}%)."
                ),
            ),
            ComplaintEvent(
                complaint_id=decided_link.target_complaint_id,
                actor_id=actor.id,
                event_type=f"LINK_{decision}",
                title=f"Cross-Bureau Link {decision.capitalize()}",
                description=f"A related case link was {decision.lower()} by {actor.full_name}.",
            ),
        ]
    )
    db.commit()
    db.refresh(decided_link)
    return decided_link
