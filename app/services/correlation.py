import json
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.ml.engine import (
    active_embedding_model_version,
    calculate_cosine_similarity,
    combine_similarity_scores,
    compute_sentence_embedding,
    compute_tfidf_similarity_scores,
    extract_shared_keywords,
    get_sentence_model,
    get_similarity_bucket,
)
from app.models.complaint import (
    CaseLink,
    Complaint,
    ComplaintEmbedding,
    ComplaintStatus,
)
from app.models.user import User
from app.services.audit import log_audit
from app.services.case_groups import group_confirmed_link
from app.services.notification import create_notification
from app.services.similarity import get_similarity_thresholds


def _complaint_text(complaint: Complaint) -> str:
    return f"{complaint.subject}. {complaint.description}"


def _get_or_create_embedding(
    db: Session, complaint: Complaint, model: object, model_name: str
) -> Optional[List[float]]:
    record = (
        db.query(ComplaintEmbedding)
        .filter(ComplaintEmbedding.complaint_id == complaint.id)
        .first()
    )
    if record and record.model_name == model_name:
        try:
            cached = json.loads(record.vector_json)
            if isinstance(cached, list) and cached:
                return cached
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Ignoring invalid cached embedding for complaint %s.",
                complaint.id,
            )

    vector = compute_sentence_embedding(_complaint_text(complaint), model=model)
    if vector is None:
        return None
    if record:
        record.vector_json = json.dumps(vector)
        record.model_name = model_name
    else:
        record = ComplaintEmbedding(
            complaint_id=complaint.id,
            model_name=model_name,
            vector_json=json.dumps(vector),
        )
        db.add(record)
    db.commit()
    return vector


def get_or_create_embedding(
    db: Session, complaint: Complaint
) -> Optional[List[float]]:
    """Return a versioned sentence embedding, or None when model loading fails."""
    model = get_sentence_model()
    if model is None:
        return None
    return _get_or_create_embedding(
        db, complaint, model, active_embedding_model_version()
    )


def _shared_metadata(
    first: Complaint, second: Complaint
) -> dict[str, str]:
    fields = {
        "category": (first.category, second.category),
        "institution": (
            first.institution_name,
            second.institution_name,
        ),
        "state": (first.institution_state, second.institution_state),
        "city": (first.institution_city, second.institution_city),
    }
    return {
        key: left.strip()
        for key, (left, right) in fields.items()
        if left and right and left.strip().casefold() == right.strip().casefold()
    }


def _hybrid_scores(
    query_text: str,
    candidate_texts: list[str],
    model: object,
    cached_query_vector: Optional[List[float]] = None,
    candidate_vectors: Optional[list[Optional[List[float]]]] = None,
) -> list[float]:
    lexical_scores = compute_tfidf_similarity_scores(query_text, candidate_texts)
    query_vector = cached_query_vector
    if model is not None and query_vector is None:
        query_vector = compute_sentence_embedding(query_text, model=model)

    scores = []
    for index, lexical_score in enumerate(lexical_scores):
        semantic_score = None
        candidate_vector = (
            candidate_vectors[index]
            if candidate_vectors is not None
            else None
        )
        if model is not None and query_vector is not None:
            if candidate_vectors is None:
                candidate_vector = compute_sentence_embedding(
                    candidate_texts[index], model=model
                )
            if candidate_vector is not None:
                try:
                    semantic_score = calculate_cosine_similarity(
                        query_vector, candidate_vector
                    )
                except ValueError as exc:
                    logger.warning(
                        "Embedding dimensions did not match; using TF-IDF for one comparison: %s",
                        exc,
                    )
        scores.append(combine_similarity_scores(lexical_score, semantic_score))
    return scores


def correlate_complaint(db: Session, complaint: Complaint) -> List[CaseLink]:
    """Create suggestions from hybrid lexical and sentence-embedding similarity."""
    other_complaints = (
        db.query(Complaint)
        .filter(Complaint.id != complaint.id)
        .all()
    )
    model = get_sentence_model()
    model_name = active_embedding_model_version()
    current_vector = (
        _get_or_create_embedding(db, complaint, model, model_name)
        if model is not None
        else None
    )
    if not other_complaints:
        return []

    other_vectors = [
        _get_or_create_embedding(db, other, model, model_name)
        if model is not None
        else None
        for other in other_complaints
    ]
    scores = _hybrid_scores(
        _complaint_text(complaint),
        [_complaint_text(other) for other in other_complaints],
        model,
        cached_query_vector=current_vector,
        candidate_vectors=other_vectors,
    )

    thresholds = get_similarity_thresholds(db)
    created_links: List[CaseLink] = []
    for other, score in zip(other_complaints, scores):
        if score < thresholds["low_threshold"]:
            continue

        existing_link = (
            db.query(CaseLink)
            .filter(
                (
                    (CaseLink.source_complaint_id == complaint.id)
                    & (CaseLink.target_complaint_id == other.id)
                )
                | (
                    (CaseLink.source_complaint_id == other.id)
                    & (CaseLink.target_complaint_id == complaint.id)
                )
            )
            .first()
        )
        if existing_link:
            continue

        shared_keywords = extract_shared_keywords(
            _complaint_text(complaint), _complaint_text(other)
        )
        new_link = CaseLink(
            source_complaint_id=complaint.id,
            target_complaint_id=other.id,
            similarity_score=round(score, 4),
            similarity_bucket=get_similarity_bucket(
                score,
                high_thresh=thresholds["high_threshold"],
                med_thresh=thresholds["medium_threshold"],
                low_thresh=thresholds["low_threshold"],
            ),
            shared_keywords=shared_keywords or None,
            shared_metadata=_shared_metadata(complaint, other),
            status="SUGGESTED",
        )
        db.add(new_link)
        created_links.append(new_link)

    db.commit()
    logger.info(
        "AI correlation generated %s suggested links for complaint %s",
        len(created_links),
        complaint.receipt_id,
    )
    return created_links


def check_intake_duplicates(
    db: Session,
    subject: str,
    description: str,
) -> Tuple[bool, str, int]:
    """Warn about likely open duplicates without returning private case details."""
    text = f"{subject}. {description}"
    open_complaints = (
        db.query(Complaint)
        .filter(Complaint.status != ComplaintStatus.CLOSED)
        .all()
    )
    if not open_complaints:
        return False, "", 0

    model = get_sentence_model()
    model_name = active_embedding_model_version()
    vectors = [
        _get_or_create_embedding(db, complaint, model, model_name)
        if model is not None
        else None
        for complaint in open_complaints
    ]
    scores = _hybrid_scores(
        text,
        [_complaint_text(complaint) for complaint in open_complaints],
        model,
        candidate_vectors=vectors,
    )
    high_threshold = get_similarity_thresholds(db)["high_threshold"]
    high_scores = [score for score in scores if score >= high_threshold]
    if high_scores:
        max_score = max(high_scores)
        return (
            True,
            f"Notice: Our AI system detected {len(high_scores)} existing active "
            f"grievance(s) with high similarity (match score ~{int(max_score * 100)}%). "
            "Your complaint will be routed and linked for consolidated review.",
            len(high_scores),
        )
    return False, "", 0


def decide_case_link(
    db: Session,
    link_id: int,
    decision: str,
    deciding_user: User,
    ip_address: Optional[str] = None,
) -> CaseLink:
    """Apply a human decision to an AI-suggested case link."""
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

    log_audit(
        db=db,
        action=f"AI_LINK_{decision}",
        entity_type="CaseLink",
        entity_id=str(link.id),
        actor_id=deciding_user.id,
        actor_email=deciding_user.email,
        ip_address=ip_address,
        before_state=before_state,
        after_state={"status": link.status, "decided_by": deciding_user.email},
    )

    if decision == "CONFIRMED":
        source_case = link.source_complaint
        target_case = link.target_complaint
        if target_case and target_case.assigned_official_id:
            create_notification(
                db=db,
                user_id=target_case.assigned_official_id,
                title="Cross-Bureau Case Link Confirmed",
                message=(
                    f"Official {deciding_user.full_name} confirmed a related case "
                    f"link between {source_case.receipt_id} and your case "
                    f"{target_case.receipt_id}."
                ),
                link=f"/cases/{target_case.id}",
            )
    return link
