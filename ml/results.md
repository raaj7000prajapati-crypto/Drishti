# Similarity Evaluation Results

- Generated: 2026-10-31T13:18:08+00:00
- Dataset: `ml/dataset.csv` (84 synthetic labelled complaint pairs)
- Labels: 35 related, 49 unrelated
- Language labels: English: 65, Hindi: 9, Hindi-English: 5, Hinglish: 5
- Scores and metrics below are computed from the labelled CSV; no metrics are simulated.

This small synthetic dataset is a smoke-test benchmark, not an estimate of production accuracy. Thresholds were evaluated against the supplied labels.

## Model availability

Skipped sentence-embedding and hybrid evaluation: configured model `paraphrase-multilingual-MiniLM-L12-v2` could not be loaded. See the warning printed by the model loader. TF-IDF results below are computed from the dataset.

## TF-IDF cosine

Best F1 threshold (searched in 0.05 increments): **0.05**

| Threshold | Precision | Recall | F1 | Accuracy | TP | FP | TN | FN |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.05 (best F1) | 0.8077 | 0.6000 | 0.6885 | 0.7738 | 21 | 5 | 44 | 14 |
| 0.30 | 0.0000 | 0.0000 | 0.0000 | 0.5833 | 0 | 0 | 49 | 35 |
| 0.50 | 0.0000 | 0.0000 | 0.0000 | 0.5833 | 0 | 0 | 49 | 35 |
| 0.80 | 0.0000 | 0.0000 | 0.0000 | 0.5833 | 0 | 0 | 49 | 35 |

Confusion matrix at the best-F1 threshold (0.05):

```text
                  Predicted unrelated  Predicted related
Actual unrelated                44                  5
Actual related                  14                 21
```
