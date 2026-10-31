import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.metrics.pairwise import cosine_similarity

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.ml.engine import (
    active_sentence_model_name,
    create_tfidf_vectorizer,
    get_sentence_model,
)

DATASET_PATH = Path(__file__).with_name("dataset.csv")
RESULTS_PATH = Path(__file__).with_name("results.md")
OPERATIONAL_THRESHOLDS = (0.30, 0.50, 0.80)
SEARCH_THRESHOLDS = tuple(round(value, 2) for value in np.arange(0.05, 1.0, 0.05))


def load_dataset(path: Path = DATASET_PATH) -> tuple[list[tuple[str, str]], list[int], dict[str, int]]:
    with path.open(encoding="utf-8-sig", newline="") as dataset_file:
        reader = csv.DictReader(dataset_file)
        required_columns = {"text_a", "text_b", "is_related", "language"}
        if not required_columns.issubset(reader.fieldnames or []):
            raise ValueError(f"Dataset must contain columns: {sorted(required_columns)}")
        rows = list(reader)

    if len(rows) < 80:
        raise ValueError(f"Expected at least 80 labelled pairs; found {len(rows)}.")

    pairs: list[tuple[str, str]] = []
    labels: list[int] = []
    languages: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=2):
        label = row["is_related"].strip()
        if label not in {"0", "1"}:
            raise ValueError(f"Invalid is_related label on CSV row {row_number}: {label!r}")
        if not row["text_a"].strip() or not row["text_b"].strip():
            raise ValueError(f"Empty complaint text on CSV row {row_number}.")
        language = (row["language"] or "").strip()
        if not language:
            raise ValueError(f"Missing language label on CSV row {row_number}.")
        pairs.append((row["text_a"].strip(), row["text_b"].strip()))
        labels.append(int(label))
        languages[language] = languages.get(language, 0) + 1

    if len(set(labels)) != 2:
        raise ValueError("Dataset must contain both related and unrelated examples.")
    return pairs, labels, languages


def tfidf_pair_scores(pairs: list[tuple[str, str]]) -> list[float]:
    texts = [text for pair in pairs for text in pair]
    vectors = create_tfidf_vectorizer().fit_transform(texts)
    return [
        float(cosine_similarity(vectors[index], vectors[index + 1])[0, 0])
        for index in range(0, len(texts), 2)
    ]


def evaluate_at_threshold(
    labels: list[int], scores: list[float], threshold: float
) -> dict[str, Any]:
    predictions = [int(score >= threshold) for score in scores]
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, predictions, average="binary", zero_division=0
    )
    tn, fp, fn, tp = confusion_matrix(labels, predictions, labels=[0, 1]).ravel()
    return {
        "threshold": threshold,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "accuracy": float(accuracy_score(labels, predictions)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def evaluate_scores(labels: list[int], scores: list[float]) -> dict[str, Any]:
    metrics = [
        evaluate_at_threshold(labels, scores, threshold)
        for threshold in SEARCH_THRESHOLDS
    ]
    return max(metrics, key=lambda row: (row["f1"], row["precision"], row["threshold"]))


def _embedding_scores(pairs: list[tuple[str, str]], model: Any) -> list[float]:
    texts = [text for pair in pairs for text in pair]
    embeddings = np.asarray(
        model.encode(
            texts,
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )
    if embeddings.ndim != 2 or embeddings.shape[0] != len(texts):
        raise ValueError("Sentence model returned an unexpected embedding shape.")
    if not np.isfinite(embeddings).all():
        raise ValueError("Sentence model returned non-finite embeddings.")
    return [
        float(np.clip(np.dot(embeddings[index], embeddings[index + 1]), 0.0, 1.0))
        for index in range(0, len(texts), 2)
    ]


def _format_model_section(name: str, scores: list[float], labels: list[int]) -> str:
    best = evaluate_scores(labels, scores)
    lines = [
        f"## {name}",
        "",
        f"Best F1 threshold (searched in 0.05 increments): **{best['threshold']:.2f}**",
        "",
        "| Threshold | Precision | Recall | F1 | Accuracy | TP | FP | TN | FN |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for threshold in sorted(set(OPERATIONAL_THRESHOLDS) | {best["threshold"]}):
        row = evaluate_at_threshold(labels, scores, threshold)
        marker = " (best F1)" if threshold == best["threshold"] else ""
        lines.append(
            f"| {threshold:.2f}{marker} | {row['precision']:.4f} | "
            f"{row['recall']:.4f} | {row['f1']:.4f} | {row['accuracy']:.4f} | "
            f"{row['tp']} | {row['fp']} | {row['tn']} | {row['fn']} |"
        )
    best_at_threshold = evaluate_at_threshold(labels, scores, best["threshold"])
    lines.extend(
        [
            "",
            f"Confusion matrix at the best-F1 threshold ({best['threshold']:.2f}):",
            "",
            "```text",
            "                  Predicted unrelated  Predicted related",
            f"Actual unrelated              {best_at_threshold['tn']:>4}               {best_at_threshold['fp']:>4}",
            f"Actual related                {best_at_threshold['fn']:>4}               {best_at_threshold['tp']:>4}",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def run_evaluation() -> str:
    pairs, labels, languages = load_dataset()
    tfidf_scores = tfidf_pair_scores(pairs)
    sections = [
        _format_model_section("TF-IDF cosine", tfidf_scores, labels)
    ]

    model_name = active_sentence_model_name()
    model = get_sentence_model()
    embedding_scores = None
    model_status = ""
    if model is None:
        model_status = (
            f"Skipped sentence-embedding and hybrid evaluation: configured model "
            f"`{model_name}` could not be loaded. See the warning printed by the "
            "model loader. TF-IDF results below are computed from the dataset."
        )
        print(f"Skipped sentence-embedding model {model_name}: unable to load.")
    else:
        try:
            embedding_scores = _embedding_scores(pairs, model)
        except Exception as exc:
            model_status = (
                f"Skipped sentence-embedding and hybrid evaluation: `{model_name}` "
                f"failed during inference ({type(exc).__name__}: {exc})."
            )
            print(model_status)
        else:
            sections.append(
                _format_model_section(
                    f"Sentence embeddings ({model_name})",
                    embedding_scores,
                    labels,
                )
            )
            hybrid_scores = [
                (tfidf * settings.SIMILARITY_TFIDF_WEIGHT)
                + (semantic * settings.SIMILARITY_EMBEDDING_WEIGHT)
                for tfidf, semantic in zip(tfidf_scores, embedding_scores)
            ]
            sections.append(
                _format_model_section("Hybrid weighted cosine", hybrid_scores, labels)
            )

    total = len(pairs)
    related = sum(labels)
    language_summary = ", ".join(
        f"{language}: {count}" for language, count in sorted(languages.items())
    )
    report = "\n".join(
        [
            "# Similarity Evaluation Results",
            "",
            f"- Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
            f"- Dataset: `ml/dataset.csv` ({total} synthetic labelled complaint pairs)",
            f"- Labels: {related} related, {total - related} unrelated",
            f"- Language labels: {language_summary}",
            "- Scores and metrics below are computed from the labelled CSV; no metrics are simulated.",
            "",
            "This small synthetic dataset is a smoke-test benchmark, not an estimate of "
            "production accuracy. Thresholds were evaluated against the supplied labels.",
            "",
            "## Model availability",
            "",
            model_status or f"Loaded `{model_name}` and computed embeddings from the dataset.",
            "",
            *sections,
        ]
    )
    RESULTS_PATH.write_text(report.rstrip() + "\n", encoding="utf-8")
    print(f"Evaluated {total} labelled pairs; wrote real metrics to {RESULTS_PATH}.")
    return report


if __name__ == "__main__":
    run_evaluation()
