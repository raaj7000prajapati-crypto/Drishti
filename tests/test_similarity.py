import pytest
from app.ml.engine import (
    calculate_cosine_similarity,
    get_similarity_bucket,
    extract_shared_keywords
)

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
