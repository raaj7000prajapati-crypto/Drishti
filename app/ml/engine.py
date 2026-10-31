import re
import json
import logging
from typing import List, Tuple, Optional, Dict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.core.config import settings

logger = logging.getLogger("drishti.ml")

# Try importing sentence_transformers with graceful fallback
SBERT_AVAILABLE = False
_sbert_model = None

try:
    from sentence_transformers import SentenceTransformer
    try:
        # Load model locally or download if network permits
        _sbert_model = SentenceTransformer("all-MiniLM-L6-v2")
        SBERT_AVAILABLE = True
        logger.info("Successfully loaded SBERT model (all-MiniLM-L6-v2)")
    except Exception as e:
        logger.warning(f"Could not load SBERT weights ({e}); falling back to Scikit-Learn TF-IDF engine")
        SBERT_AVAILABLE = False
except ImportError:
    logger.info("sentence-transformers not installed; using Scikit-Learn TF-IDF engine")
    SBERT_AVAILABLE = False

# High quality TF-IDF Fallback Vectorizer
_tfidf_vectorizer = TfidfVectorizer(
    stop_words="english",
    ngram_range=(1, 2),
    max_features=512,
    sublinear_tf=True
)
_fitted_corpus: List[str] = [
    "faculty salary unpaid arrears aiCTE norms approval affiliation infrastructure laboratory equipment",
    "capitation fee refund admission cancellation harassment ragging hostel mess attendance",
    "fake degree unauthorized intake building plan violation delayed exams evaluation scam"
]
_tfidf_vectorizer.fit(_fitted_corpus)

def clean_text(text: str) -> str:
    """Preprocess and normalize complaint text."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def compute_embedding(text: str, force_model: Optional[str] = None) -> Tuple[List[float], str]:
    """
    Computes semantic vector embedding for given text.
    Returns: (embedding_vector, model_name)
    """
    cleaned = clean_text(text)
    if not cleaned:
        cleaned = "empty complaint"

    use_sbert = SBERT_AVAILABLE and (force_model != "tfidf")
    if force_model == "sbert" and not SBERT_AVAILABLE:
        use_sbert = False

    if use_sbert and _sbert_model is not None:
        try:
            vec = _sbert_model.encode(cleaned, convert_to_numpy=True, normalize_embeddings=True)
            return vec.tolist(), "all-MiniLM-L6-v2"
        except Exception as e:
            logger.warning(f"SBERT inference failed: {e}; using TF-IDF fallback")

    # TF-IDF Fallback
    try:
        tfidf_vec = _tfidf_vectorizer.transform([cleaned]).toarray()[0]
        # Normalize to unit vector for fast cosine similarity
        norm = np.linalg.norm(tfidf_vec)
        if norm > 0:
            tfidf_vec = tfidf_vec / norm
        return tfidf_vec.tolist(), "tfidf-sklearn-cosine"
    except Exception as e:
        logger.error(f"TF-IDF vectorizer error: {e}")
        return [0.0] * 512, "tfidf-fallback"

def calculate_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    a = np.array(vec_a, dtype=np.float32)
    b = np.array(vec_b, dtype=np.float32)
    
    dot_prod = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    sim = dot_prod / (norm_a * norm_b)
    return float(np.clip(sim, 0.0, 1.0))

def get_similarity_bucket(
    score: float,
    high_thresh: Optional[float] = None,
    med_thresh: Optional[float] = None,
    low_thresh: Optional[float] = None
) -> str:
    """
    Categorize similarity into buckets:
    - High: >= 0.80
    - Medium: 0.50 - 0.79
    - Low: 0.30 - 0.49
    - Minimal: < 0.30
    """
    high = high_thresh if high_thresh is not None else settings.SIMILARITY_HIGH_THRESHOLD
    med = med_thresh if med_thresh is not None else settings.SIMILARITY_MEDIUM_THRESHOLD
    low = low_thresh if low_thresh is not None else settings.SIMILARITY_LOW_THRESHOLD

    if score >= high:
        return "High"
    elif score >= med:
        return "Medium"
    elif score >= low:
        return "Low"
    else:
        return "Minimal"

def extract_shared_keywords(text_a: str, text_b: str, max_keywords: int = 5) -> str:
    """
    Extracts top overlapping significant terms between two complaints
    to explain the 'Why Matched' reason.
    """
    stop_words = {
        "the", "and", "for", "with", "that", "this", "from", "are", "have", "not",
        "been", "were", "they", "will", "would", "their", "there", "about", "which",
        "regarding", "complaint", "aicte", "institution", "college", "student", "please"
    }
    
    words_a = set(re.findall(r'\b[a-z]{4,}\b', text_a.lower())) - stop_words
    words_b = set(re.findall(r'\b[a-z]{4,}\b', text_b.lower())) - stop_words
    
    common = list(words_a.intersection(words_b))
    if not common:
        return "Shared category or institutional profile"
    
    # Sort by word length as proxy for specificity
    common.sort(key=lambda w: len(w), reverse=True)
    return ", ".join(common[:max_keywords])
