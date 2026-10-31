import uuid

from app.core.security import create_access_token
from app.models.complaint import CaseLink, Complaint, ComplaintEmbedding
from app.models.user import Role, User
from app.services import correlation


def _admin_headers(user):
    token = create_access_token(
        {"sub": user.email, "role": user.role.value, "id": user.id}
    )
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_update_persisted_similarity_thresholds(client, db_session):
    suffix = uuid.uuid4().hex
    admin = User(
        email=f"phase-c-admin-{suffix}@example.test",
        hashed_password="not-used",
        full_name="Phase C Admin",
        role=Role.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    headers = _admin_headers(admin)

    updated = client.put(
        "/api/v1/admin/similarity-thresholds",
        headers=headers,
        json={
            "high_threshold": 0.9,
            "medium_threshold": 0.6,
            "low_threshold": 0.25,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["high_threshold"] == 0.9

    loaded = client.get(
        "/api/v1/admin/similarity-thresholds", headers=headers
    )
    assert loaded.status_code == 200
    assert loaded.json()["medium_threshold"] == 0.6

    invalid = client.put(
        "/api/v1/admin/similarity-thresholds",
        headers=headers,
        json={
            "high_threshold": 0.6,
            "medium_threshold": 0.7,
            "low_threshold": 0.2,
        },
    )
    assert invalid.status_code == 422

    complainant = User(
        email=f"phase-c-reader-{suffix}@example.test",
        hashed_password="not-used",
        full_name="Non-admin",
        role=Role.COMPLAINANT,
        is_active=True,
    )
    db_session.add(complainant)
    db_session.commit()
    denied = client.get(
        "/api/v1/admin/similarity-thresholds",
        headers=_admin_headers(complainant),
    )
    assert denied.status_code == 403


def test_cached_embeddings_are_recomputed_for_changed_model(db_session, monkeypatch):
    suffix = uuid.uuid4().hex
    user = User(
        email=f"phase-c-complainant-{suffix}@example.test",
        hashed_password="not-used",
        full_name="Phase C Complainant",
        role=Role.COMPLAINANT,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    complaint = Complaint(
        receipt_id=f"PHASE-C-{suffix}",
        complainant_id=user.id,
        institution_name="Example Institute",
        institution_state="Delhi",
        institution_city="New Delhi",
        category="Fees",
        subject="Refund not received",
        description="The institute has not refunded the fee.",
    )
    db_session.add(complaint)
    db_session.commit()
    model_names = ["model-v1", "model-v2"]
    vectors = iter(([1.0, 0.0], [0.0, 1.0]))

    monkeypatch.setattr(correlation, "get_sentence_model", lambda: object())
    monkeypatch.setattr(
        correlation, "active_embedding_model_version", lambda: model_names[0]
    )
    monkeypatch.setattr(
        correlation,
        "compute_sentence_embedding",
        lambda _text, model=None: list(next(vectors)),
    )

    first = correlation.get_or_create_embedding(db_session, complaint)
    model_names[0] = "model-v2"
    second = correlation.get_or_create_embedding(db_session, complaint)

    record = (
        db_session.query(ComplaintEmbedding)
        .filter(ComplaintEmbedding.complaint_id == complaint.id)
        .one()
    )
    assert first == [1.0, 0.0]
    assert second == [0.0, 1.0]
    assert record.model_name == "model-v2"


def test_case_link_response_includes_shared_metadata_for_admin(client, db_session):
    suffix = uuid.uuid4().hex
    admin = User(
        email=f"phase-c-link-admin-{suffix}@example.test",
        hashed_password="not-used",
        full_name="Phase C Admin",
        role=Role.ADMIN,
        is_active=True,
    )
    db_session.add(admin)
    db_session.flush()
    cases = [
        Complaint(
            receipt_id=f"PHASE-C-LINK-{suffix}-{index}",
            complainant_id=admin.id,
            institution_name="Apex Institute",
            institution_state="Delhi",
            institution_city="New Delhi",
            category="Fees",
            subject=f"Fee complaint {index}",
            description="Unpaid fee refund",
        )
        for index in range(2)
    ]
    db_session.add_all(cases)
    db_session.flush()
    db_session.add(
        CaseLink(
            source_complaint_id=cases[0].id,
            target_complaint_id=cases[1].id,
            similarity_score=0.7,
            similarity_bucket="Medium",
            shared_keywords="fee, refund",
            shared_metadata={"category": "Fees", "state": "Delhi"},
        )
    )
    db_session.commit()

    response = client.get(
        f"/api/v1/complaints/{cases[0].id}",
        headers=_admin_headers(admin),
    )

    assert response.status_code == 200
    link = response.json()["suggested_links"][0]
    assert link["shared_metadata"] == {"category": "Fees", "state": "Delhi"}


def test_evaluator_skips_unavailable_model_and_writes_real_tfidf_metrics(
    tmp_path, monkeypatch, capsys
):
    from ml import evaluate

    result_path = tmp_path / "metrics.md"
    monkeypatch.setattr(evaluate, "RESULTS_PATH", result_path)
    monkeypatch.setattr(evaluate, "get_sentence_model", lambda: None)

    report = evaluate.run_evaluation()

    assert "Skipped sentence-embedding and hybrid evaluation" in report
    assert "TF-IDF cosine" in report
    assert "Confusion matrix" in report
    assert "simulated" in report
    assert "84 synthetic labelled complaint pairs" in report
    assert result_path.read_text(encoding="utf-8") == report.rstrip() + "\n"
    assert "Skipped sentence-embedding model" in capsys.readouterr().out
