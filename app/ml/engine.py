import importlib.util
import logging
import re
import unicodedata
from functools import lru_cache
from typing import Any, List, Optional, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings

logger = logging.getLogger("drishti.ml")
SBERT_AVAILABLE = importlib.util.find_spec("sentence_transformers") is not None
_failed_models: set[str] = set()


@lru_cache(maxsize=2)
def _load_sentence_model(model_name: str) -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def get_sentence_model(multilingual: Optional[bool] = None) -> Any:
    """Load the configured sentence model lazily; None means use TF-IDF only."""
    use_multilingual = (
        settings.SIMILARITY_MULTILINGUAL_ENABLED
        if multilingual is None
        else multilingual
    )
    model_name = (
        settings.SIMILARITY_MULTILINGUAL_MODEL
        if use_multilingual
        else settings.SIMILARITY_ENGLISH_MODEL
    )
    if model_name in _failed_models:
        return None
    try:
        return _load_sentence_model(model_name)
    except Exception as exc:
        if model_name not in _failed_models:
            logger.warning(
                "Could not load sentence model %s (%s); using TF-IDF similarity.",
                model_name,
                exc,
            )
            _failed_models.add(model_name)
        return None


def active_sentence_model_name(multilingual: Optional[bool] = None) -> str:
    use_multilingual = (
        settings.SIMILARITY_MULTILINGUAL_ENABLED
        if multilingual is None
        else multilingual
    )
    return (
        settings.SIMILARITY_MULTILINGUAL_MODEL
        if use_multilingual
        else settings.SIMILARITY_ENGLISH_MODEL
    )


def active_embedding_model_version(multilingual: Optional[bool] = None) -> str:
    return (
        f"{active_sentence_model_name(multilingual)}"
        f"@{settings.SIMILARITY_EMBEDDING_CACHE_VERSION}"
    )


def clean_text(text: str) -> str:
    """Normalize whitespace and punctuation while preserving Unicode words."""
    if not text:
        return ""
    text = text.lower()
    normalized = "".join(
        character
        if character.isalnum()
        or character.isspace()
        or unicodedata.category(character).startswith("M")
        else " "
        for character in text
    )
    return re.sub(r"\s+", " ", normalized).strip()


def create_tfidf_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        stop_words="english",
        token_pattern=r"(?u)[\w\u0900-\u097f]+",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )


def compute_sentence_embedding(
    text: str, model: Any = None, multilingual: Optional[bool] = None
) -> Optional[List[float]]:
    model = model if model is not None else get_sentence_model(multilingual)
    if model is None:
        return None
    try:
        vector = np.asarray(
            model.encode(
                clean_text(text),
                convert_to_numpy=True,
                normalize_embeddings=True,
            ),
            dtype=np.float32,
        ).reshape(-1)
        if vector.size == 0 or not np.isfinite(vector).all():
            raise ValueError("model returned an empty or non-finite vector")
        return vector.tolist()
    except Exception as exc:
        logger.warning("Sentence embedding inference failed; using TF-IDF: %s", exc)
        return None


def compute_tfidf_similarity_scores(
    query: str, candidate_texts: Sequence[str]
) -> List[float]:
    """Compute one query-to-candidate cosine score for a multilingual text batch."""
    if not candidate_texts:
        return []
    texts = [clean_text(query), *(clean_text(text) for text in candidate_texts)]
    if not any(texts):
        return [0.0] * len(candidate_texts)
    vectorizer = create_tfidf_vectorizer()
    try:
        vectors = vectorizer.fit_transform(texts)
    except ValueError as exc:
        if "empty vocabulary" not in str(exc).lower():
            raise
        return [0.0] * len(candidate_texts)
    return cosine_similarity(vectors[0:1], vectors[1:]).ravel().tolist()


def calculate_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    a = np.asarray(vec_a, dtype=np.float32).reshape(-1)
    b = np.asarray(vec_b, dtype=np.float32).reshape(-1)
    if a.shape != b.shape:
        raise ValueError("Embedding vectors must have matching dimensions.")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Embedding vectors must contain only finite values.")
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / (norm_a * norm_b), 0.0, 1.0))


def combine_similarity_scores(
    tfidf_score: float,
    embedding_score: Optional[float],
    tfidf_weight: Optional[float] = None,
    embedding_weight: Optional[float] = None,
) -> float:
    lexical_weight = (
        settings.SIMILARITY_TFIDF_WEIGHT
        if tfidf_weight is None
        else tfidf_weight
    )
    semantic_weight = (
        settings.SIMILARITY_EMBEDDING_WEIGHT
        if embedding_weight is None
        else embedding_weight
    )
    if embedding_score is None:
        return float(np.clip(tfidf_score, 0.0, 1.0))
    total = lexical_weight + semantic_weight
    if total <= 0:
        raise ValueError("At least one similarity weight must be positive.")
    return float(
        np.clip(
            (tfidf_score * lexical_weight + embedding_score * semantic_weight)
            / total,
            0.0,
            1.0,
        )
    )


def get_similarity_bucket(
    score: float,
    high_thresh: Optional[float] = None,
    med_thresh: Optional[float] = None,
    low_thresh: Optional[float] = None,
) -> str:
    high = high_thresh if high_thresh is not None else settings.SIMILARITY_HIGH_THRESHOLD
    med = med_thresh if med_thresh is not None else settings.SIMILARITY_MEDIUM_THRESHOLD
    low = low_thresh if low_thresh is not None else settings.SIMILARITY_LOW_THRESHOLD
    if not 0 <= low < med < high <= 1:
        raise ValueError("Similarity thresholds must satisfy 0 <= low < medium < high <= 1.")
    if score >= high:
        return "High"
    if score >= med:
        return "Medium"
    if score >= low:
        return "Low"
    return "Minimal"


def extract_shared_keywords(
    text_a: str, text_b: str, max_keywords: int = 5
) -> str:
    stop_words = {
        "the", "and", "for", "with", "that", "this", "from", "are", "have", "not",
        "been", "were", "they", "will", "would", "their", "there", "about", "which",
        "regarding", "complaint", "aicte", "institution", "college", "student",
        "please", "का", "की", "के", "और", "में", "को", "से", "है", "हैं",
        "पर", "यह", "था", "थे", "कर", "रहा", "रही", "लिए",
    }
    def tokens(text: str) -> set[str]:
        token_list = []
        token = []
        for character in clean_text(text):
            if (
                character.isalnum()
                or unicodedata.category(character).startswith("M")
            ):
                token.append(character)
            elif token:
                token_list.append("".join(token))
                token = []
        if token:
            token_list.append("".join(token))
        return {word for word in token_list if len(word) >= 3}

    words_a = tokens(text_a)
    words_b = tokens(text_b)
    common = words_a.intersection(words_b) - stop_words
    return ", ".join(sorted(common, key=lambda word: (-len(word), word))[:max_keywords])
