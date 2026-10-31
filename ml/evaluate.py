import csv
import sys
from datetime import datetime, timezone
from html import escape
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

from app.ml.engine import (
    active_sentence_model_name,
    create_tfidf_vectorizer,
    get_sentence_model,
)

DATASET_PATH = Path(__file__).with_name("dataset.csv")
RESULTS_PATH = Path(__file__).with_name("results.md")
CHART_PATH = Path(__file__).with_name("results-chart.svg")
OPERATIONAL_THRESHOLDS = (0.30, 0.50, 0.80)
SEARCH_THRESHOLDS = tuple(round(value, 2) for value in np.arange(0.05, 1.0, 0.05))
WEIGHT_SEARCH = tuple(round(value, 2) for value in np.arange(0.0, 1.01, 0.05))


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


def select_hybrid_weights(
    labels: list[int], tfidf_scores: list[float], embedding_scores: list[float]
) -> tuple[float, float, list[float], dict[str, Any]]:
    candidates = []
    for embedding_weight in WEIGHT_SEARCH:
        tfidf_weight = round(1.0 - embedding_weight, 2)
        scores = [
            (tfidf * tfidf_weight) + (semantic * embedding_weight)
            for tfidf, semantic in zip(tfidf_scores, embedding_scores)
        ]
        best = evaluate_scores(labels, scores)
        candidates.append(
            (best, tfidf_weight, embedding_weight, scores)
        )
    best, tfidf_weight, embedding_weight, scores = max(
        candidates,
        key=lambda candidate: (
            candidate[0]["f1"],
            candidate[0]["precision"],
            candidate[0]["recall"],
            candidate[1],
        ),
    )
    return tfidf_weight, embedding_weight, scores, best


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


def _write_metrics_chart(metrics: list[tuple[str, dict[str, Any]]]) -> None:
    width = 760
    chart_left = 230
    chart_width = 480
    row_height = 76
    top = 72
    colors = {"precision": "#2563eb", "recall": "#16a34a", "f1": "#ea580c"}
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{top + row_height * len(metrics) + 35}" viewBox="0 0 {width} '
        f'{top + row_height * len(metrics) + 35}" role="img">',
        "<title>Precision, recall, and F1 by model</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="34" font-family="Arial,sans-serif" font-size="20" '
        'font-weight="700" fill="#111827">Best-threshold metrics</text>',
    ]
    for index, (metric, color) in enumerate(colors.items()):
        x = chart_left + index * 155
        lines.extend(
            [
                f'<rect x="{x}" y="48" width="12" height="12" fill="{color}"/>',
                f'<text x="{x + 18}" y="59" font-family="Arial,sans-serif" '
                f'font-size="13" fill="#374151">{metric.title()}</text>',
            ]
        )

    for tick in range(0, 11, 2):
        x = chart_left + chart_width * tick / 10
        lines.extend(
            [
                f'<line x1="{x:.1f}" y1="{top - 8}" x2="{x:.1f}" '
                f'y2="{top + row_height * len(metrics) - 13}" '
                'stroke="#e5e7eb"/>',
                f'<text x="{x:.1f}" y="{top + row_height * len(metrics) + 5}" '
                'text-anchor="middle" font-family="Arial,sans-serif" '
                f'font-size="11" fill="#6b7280">{tick / 10:.1f}</text>',
            ]
        )

    for row_index, (name, values) in enumerate(metrics):
        y = top + row_index * row_height
        lines.append(
            f'<text x="20" y="{y + 22}" font-family="Arial,sans-serif" '
            f'font-size="13" fill="#111827">{escape(name)}</text>'
        )
        for metric_index, (metric, color) in enumerate(colors.items()):
            bar_y = y + metric_index * 17
            value = values[metric]
            bar_width = chart_width * value
            lines.extend(
                [
                    f'<rect x="{chart_left}" y="{bar_y}" width="{bar_width:.2f}" '
                    f'height="12" rx="2" fill="{color}"/>',
                    f'<text x="{chart_left + bar_width + 5:.2f}" y="{bar_y + 10}" '
                    'font-family="Arial,sans-serif" font-size="10" '
                    f'fill="#374151">{value:.3f}</text>',
                ]
            )
    lines.append("</svg>")
    CHART_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    chart_metrics = [("TF-IDF cosine", evaluate_scores(labels, tfidf_scores))]

    model_name = active_sentence_model_name()
    model = get_sentence_model()
    embedding_scores = None
    model_status = ""
    weight_status = "Not evaluated because sentence embeddings were unavailable."
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
            embedding_metrics = evaluate_scores(labels, embedding_scores)
            sections.append(
                _format_model_section(
                    f"Sentence embeddings ({model_name})",
                    embedding_scores,
                    labels,
                )
            )
            chart_metrics.append(("Sentence embeddings", embedding_metrics))
            tfidf_weight, embedding_weight, hybrid_scores, hybrid_metrics = (
                select_hybrid_weights(labels, tfidf_scores, embedding_scores)
            )
            weight_status = (
                f"Selected **{tfidf_weight:.2f} TF-IDF / {embedding_weight:.2f} "
                f"embedding** after evaluating all weight pairs in 0.05 increments "
                f"from 0.00/1.00 through 1.00/0.00. At each pair, the best threshold "
                f"was chosen by F1; weight pairs were ranked by F1, precision, recall, "
                f"then TF-IDF weight. The selected in-sample result is "
                f"F1 {hybrid_metrics['f1']:.4f} at threshold "
                f"{hybrid_metrics['threshold']:.2f}. This is exploratory tuning and "
                f"not independent validation."
            )
            sections.append(
                _format_model_section("Hybrid weighted cosine", hybrid_scores, labels)
            )
            chart_metrics.append(("Hybrid weighted cosine", hybrid_metrics))
    _write_metrics_chart(chart_metrics)

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
            "## Hybrid weight selection",
            "",
            weight_status,
            "",
            "![Measured precision, recall, and F1 by model](./results-chart.svg)",
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
