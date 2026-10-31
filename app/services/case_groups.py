from sqlalchemy.orm import Session

from app.models.case_group import CaseGroup, CaseGroupMember
from app.models.complaint import CaseLink


def group_confirmed_link(db: Session, link: CaseLink, actor_id: int) -> CaseGroup:
    """Ensure both complaints in a confirmed link belong to the same group."""
    source_membership = (
        db.query(CaseGroupMember)
        .filter(CaseGroupMember.complaint_id == link.source_complaint_id)
        .with_for_update()
        .first()
    )
    target_membership = (
        db.query(CaseGroupMember)
        .filter(CaseGroupMember.complaint_id == link.target_complaint_id)
        .with_for_update()
        .first()
    )

    if source_membership is None and target_membership is None:
        group = CaseGroup(created_by_id=actor_id)
        db.add(group)
        db.flush()
        db.add_all(
            [
                CaseGroupMember(
                    case_group_id=group.id,
                    complaint_id=link.source_complaint_id,
                    added_by_id=actor_id,
                ),
                CaseGroupMember(
                    case_group_id=group.id,
                    complaint_id=link.target_complaint_id,
                    added_by_id=actor_id,
                ),
            ]
        )
        return group

    if source_membership is None:
        group = target_membership.group
        db.add(
            CaseGroupMember(
                case_group_id=group.id,
                complaint_id=link.source_complaint_id,
                added_by_id=actor_id,
            )
        )
        return group

    if target_membership is None:
        group = source_membership.group
        db.add(
            CaseGroupMember(
                case_group_id=group.id,
                complaint_id=link.target_complaint_id,
                added_by_id=actor_id,
            )
        )
        return group

    if source_membership.case_group_id == target_membership.case_group_id:
        return source_membership.group

    primary = source_membership.group
    secondary = target_membership.group
    secondary_memberships = (
        db.query(CaseGroupMember)
        .filter(CaseGroupMember.case_group_id == secondary.id)
        .with_for_update()
        .all()
    )
    for membership in secondary_memberships:
        membership.group = primary
    db.flush()
    db.delete(secondary)
    return primary
