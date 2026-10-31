from typing import Optional

from sqlalchemy.orm import Session, joinedload

from app.models.bureau import Bureau
from app.models.complaint import CaseLink, Complaint, InformationRequest
from app.models.user import User


def get_bureau_by_id(db: Session, bureau_id: int) -> Bureau | None:
    return db.query(Bureau).filter(Bureau.id == bureau_id).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_pending_information_request(
    db: Session,
    complaint_id: int,
    request_id: Optional[int] = None,
) -> InformationRequest | None:
    query = db.query(InformationRequest).filter(
        InformationRequest.complaint_id == complaint_id,
        InformationRequest.status == "PENDING",
    )
    if request_id is not None:
        query = query.filter(InformationRequest.id == request_id)
    return query.with_for_update().first()


def get_case_link_for_update(db: Session, link_id: int) -> CaseLink | None:
    return (
        db.query(CaseLink)
        .options(
            joinedload(CaseLink.source_complaint),
            joinedload(CaseLink.target_complaint),
        )
        .filter(CaseLink.id == link_id)
        .with_for_update()
        .first()
    )
