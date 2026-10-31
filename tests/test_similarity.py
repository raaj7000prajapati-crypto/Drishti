import pytest
import logging
from types import SimpleNamespace

from app.ml import engine
from app.ml.engine import (
    combine_similarity_scores,
    calculate_cosine_similarity,
    compute_tfidf_similarity_scores,
    get_similarity_bucket,
    extract_shared_keywords,
)
from app.services.correlation import _shared_metadata

def test_similarity_bucketing():
    assert get_similarity_bucket(0.85) == "High"
    assert get_similarity_bucket(0.80) == "High"
    assert get_similarity_bucket(0.79) == "Medium"
    assert get_similarity_bucket(0.50) == "Medium"
    assert get_similarity_bucket(0.49) == "Low"
    assert get_similarity_bucket(0.30) == "Low"
    assert get_similarity_bucket(0.29) == "Minimal"
    assert get_similarity_bucket(0.05) == "Minimal"

def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert calculate_cosine_similarity(v1, v2) == pytest.approx(1.0, 0.001)
    assert calculate_cosine_similarity(v1, v3) == pytest.approx(0.0, 0.001)

def test_shared_keywords_extraction():
    text_a = "The capitation fee demanded for admission at apex engineering institute is illegal"
    text_b = "Students facing extortion of capitation fee and original document withholding at admission office"
    keywords = extract_shared_keywords(text_a, text_b)
    assert "capitation" in keywords or "admission" in keywords


def test_tfidf_similarity_supports_unicode_and_hindi_text():
    scores = compute_tfidf_similarity_scores(
        "कॉलेज ने फीस वापस नहीं की",
        ["कॉलेज ने फीस वापस करने से मना किया", "छात्रावास में पानी की समस्या है"],
    )
    assert scores[0] > scores[1]


def test_hybrid_weights_and_tfidf_fallback():
    assert combine_similarity_scores(0.2, 0.8, 0.35, 0.65) == pytest.approx(0.59)
    assert combine_similarity_scores(0.42, None, 0.35, 0.65) == pytest.approx(0.42)


def test_model_load_failure_warns_and_returns_tfidf_fallback(monkeypatch, caplog):
    model_name = "missing-model-for-test"
    monkeypatch.setattr(engine.settings, "SIMILARITY_MULTILINGUAL_MODEL", model_name)
    monkeypatch.setattr(engine, "_failed_models", set())

    def fail_load(_model_name):
        raise OSError("model weights unavailable")

    monkeypatch.setattr(engine, "_load_sentence_model", fail_load)
    with caplog.at_level(logging.WARNING, logger="drishti.ml"):
        assert engine.get_sentence_model(multilingual=True) is None

    assert "using TF-IDF similarity" in caplog.text


def test_sentence_embeddings_use_selected_multilingual_model():
    class FakeModel:
        def encode(self, text, **_kwargs):
            assert "शिकायत" in text
            return [3.0, 4.0]

    vector = engine.compute_sentence_embedding(
        "शिकायत दर्ज है", model=FakeModel()
    )
    assert vector == pytest.approx([3.0, 4.0])


def test_model_selection_supports_multilingual_and_english(monkeypatch):
    monkeypatch.setattr(engine.settings, "SIMILARITY_MULTILINGUAL_ENABLED", True)
    assert engine.active_sentence_model_name() == engine.settings.SIMILARITY_MULTILINGUAL_MODEL
    assert engine.active_sentence_model_name(multilingual=False) == engine.settings.SIMILARITY_ENGLISH_MODEL


def test_bucket_thresholds_can_be_configured():
    assert get_similarity_bucket(
        0.72, high_thresh=0.9, med_thresh=0.7, low_thresh=0.4
    ) == "Medium"
    with pytest.raises(ValueError, match="low < medium < high"):
        get_similarity_bucket(0.5, high_thresh=0.5, med_thresh=0.6, low_thresh=0.3)


def test_shared_metadata_explains_only_matching_fields():
    first = SimpleNamespace(
        category="Fees",
        institution_name="Apex College",
        institution_state="Delhi",
        institution_city="New Delhi",
    )
    second = SimpleNamespace(
        category="Fees",
        institution_name="Different College",
        institution_state="Delhi",
        institution_city="Gurgaon",
    )
    assert _shared_metadata(first, second) == {
        "category": "Fees",
        "state": "Delhi",
    }


def test_real_metric_calculation_returns_confusion_matrix_counts():
    from ml.evaluate import evaluate_at_threshold

    result = evaluate_at_threshold(
        labels=[0, 0, 1, 1],
        scores=[0.1, 0.8, 0.6, 0.9],
        threshold=0.5,
    )
    assert (result["tn"], result["fp"], result["fn"], result["tp"]) == (1, 1, 0, 2)
