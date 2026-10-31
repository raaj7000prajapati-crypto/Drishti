import json
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from app.models.complaint import Complaint, CaseLink, ComplaintEmbedding, ComplaintStatus
from app.models.user import User
from app.models.audit import AuditLog
from app.ml.engine import (
    compute_embedding, calculate_cosine_similarity,
    get_similarity_bucket, extract_shared_keywords
)
from app.services.notification import create_notification
from app.services.audit import log_audit
from app.services.case_groups import group_confirmed_link
from app.core.config import settings
from app.core.logging import logger

def get_or_create_embedding(db: Session, complaint: Complaint) -> List[float]:
    """Retrieve cached embedding or compute and save new embedding in DB."""
    record = db.query(ComplaintEmbedding).filter(ComplaintEmbedding.complaint_id == complaint.id).first()
    if record and record.vector_json:
        try:
            return json.loads(record.vector_json)
        except Exception:
            pass

    text_to_embed = f"{complaint.subject}. {complaint.description}"
    vector, model_name = compute_embedding(text_to_embed)

    if record:
        record.vector_json = json.dumps(vector)
        record.model_name = model_name
    else:
        record = ComplaintEmbedding(
            complaint_id=complaint.id,
            model_name=model_name,
            vector_json=json.dumps(vector)
        )
        db.add(record)
    
    db.commit()
    return vector

def correlate_complaint(db: Session, complaint: Complaint) -> List[CaseLink]:
    """
    Computes cross-bureau cosine similarity against all other existing complaints.
    Generates suggested CaseLink records for scores >= Low threshold (0.30).
    """
    current_vec = get_or_create_embedding(db, complaint)
    
    # Query all other complaints
    other_complaints = (
        db.query(Complaint)
        .filter(Complaint.id != complaint.id)
        .all()
    )

    created_links: List[CaseLink] = []

    for other in other_complaints:
        other_vec = get_or_create_embedding(db, other)
        score = calculate_cosine_similarity(current_vec, other_vec)
        
        # Only suggest links if similarity is at least Low (>= 0.30)
        if score >= settings.SIMILARITY_LOW_THRESHOLD:
            bucket = get_similarity_bucket(score)
            shared_kws = extract_shared_keywords(
                f"{complaint.subject} {complaint.description}",
                f"{other.subject} {other.description}"
            )

            # Check if link already exists in either direction
            existing_link = (
                db.query(CaseLink)
                .filter(
                    ((CaseLink.source_complaint_id == complaint.id) & (CaseLink.target_complaint_id == other.id)) |
                    ((CaseLink.source_complaint_id == other.id) & (CaseLink.target_complaint_id == complaint.id))
                )
                .first()
            )

            if not existing_link:
                new_link = CaseLink(
                    source_complaint_id=complaint.id,
                    target_complaint_id=other.id,
                    similarity_score=round(score, 4),
                    similarity_bucket=bucket,
                    shared_keywords=shared_kws,
                    status="SUGGESTED"
                )
                db.add(new_link)
                created_links.append(new_link)

    db.commit()
    logger.info(f"AI Correlation generated {len(created_links)} suggested links for complaint {complaint.receipt_id}")
    return created_links

def check_intake_duplicates(
    db: Session,
    subject: str,
    description: str
) -> Tuple[bool, str, int]:
    """
    Intake check: checks if a High-similarity open case already exists,
    providing a duplicate warning without exposing private data.
    """
    text = f"{subject}. {description}"
    query_vec, _ = compute_embedding(text)

    # Check against non-closed complaints
    open_complaints = (
        db.query(Complaint)
        .filter(Complaint.status != ComplaintStatus.CLOSED)
        .all()
    )

    match_count = 0
    max_score = 0.0

    for c in open_complaints:
        emb = get_or_create_embedding(db, c)
        score = calculate_cosine_similarity(query_vec, emb)
        if score >= settings.SIMILARITY_HIGH_THRESHOLD:
            match_count += 1
            if score > max_score:
                max_score = score

    if match_count > 0:
        return (
            True,
            f"Notice: Our AI system detected {match_count} existing active grievance(s) with high similarity (match score ~{int(max_score*100)}%). Your complaint will be routed and linked for consolidated review.",
            match_count
        )
    return False, "", 0

def decide_case_link(
    db: Session,
    link_id: int,
    decision: str,  # "CONFIRMED" or "REJECTED"
    deciding_user: User,
    ip_address: Optional[str] = None
) -> CaseLink:
    """
    Human-in-the-loop decision for AI-suggested case links.
    Only confirmed links create a case group and notify the other bureau's official.
    Logs every action in the immutable audit log.
    """
    link = db.query(CaseLink).filter(CaseLink.id == link_id).with_for_update().first()
    if not link:
        raise ValueError(f"Case link {link_id} not found")

    from datetime import datetime, timezone
    before_state = {"status": link.status, "similarity_score": link.similarity_score}
    
    link.status = decision
    link.decided_by_id = deciding_user.id
    link.decided_at = datetime.now(timezone.utc)
    if decision == "CONFIRMED":
        group_confirmed_link(db, link, deciding_user.id)
    db.commit()
    db.refresh(link)

    # Audit log
    log_audit(
        db=db,
        action=f"AI_LINK_{decision}",
        entity_type="CaseLink",
        entity_id=str(link.id),
        actor_id=deciding_user.id,
        actor_email=deciding_user.email,
        ip_address=ip_address,
        before_state=before_state,
        after_state={"status": link.status, "decided_by": deciding_user.email}
    )

    # If CONFIRMED, notify the official handling the target complaint if across bureaus
    if decision == "CONFIRMED":
        source_case = link.source_complaint
        target_case = link.target_complaint
        
        if target_case and target_case.assigned_official_id:
            create_notification(
                db=db,
                user_id=target_case.assigned_official_id,
                title="Cross-Bureau Case Link Confirmed",
                message=f"Official {deciding_user.full_name} confirmed a related case link between {source_case.receipt_id} and your case {target_case.receipt_id}.",
                link=f"/cases/{target_case.id}"
            )

    return link
