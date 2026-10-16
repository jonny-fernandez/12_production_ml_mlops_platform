"""CP13 delayed-label, aggregate performance checks, never invented outcomes."""
from __future__ import annotations
import math
import numpy as np
from sklearn.metrics import (roc_auc_score, average_precision_score,
                             brier_score_loss, precision_score, recall_score, f1_score)


def evaluate_recent_predictions(actual=None, probabilities=None, *, threshold: float = 0.125,
                                minimum_labeled: int = 500) -> dict:
    if actual is None or probabilities is None:
        return {"format": "project12_cp13_performance_v1", "status": "NO_MATURE_LABELS",
                "labeled_rows": 0, "metrics": None}
    truth = np.asarray(list(actual))
    prob = np.asarray(list(probabilities), dtype=float)
    if truth.ndim != 1 or prob.ndim != 1 or len(truth) != len(prob):
        raise ValueError("Actual labels and probabilities must be aligned vectors")
    if not np.isin(truth, [0, 1]).all() or not np.isfinite(prob).all() or ((prob < 0) | (prob > 1)).any():
        raise ValueError("Labels must be binary and probabilities finite in [0,1]")
    if not 0 < threshold < 1 or minimum_labeled < 1:
        raise ValueError("Invalid threshold or minimum sample")
    if len(truth) < minimum_labeled or len(set(truth.tolist())) < 2:
        return {"format": "project12_cp13_performance_v1", "status": "INCONCLUSIVE",
                "labeled_rows": len(truth), "metrics": None}
    predicted = (prob >= threshold).astype(int)
    return {"format": "project12_cp13_performance_v1", "status": "MEASURED", "labeled_rows": len(truth),
            "threshold": threshold, "metrics": {
                "roc_auc": round(float(roc_auc_score(truth, prob)), 6),
                "pr_auc": round(float(average_precision_score(truth, prob)), 6),
                "brier_score": round(float(brier_score_loss(truth, prob)), 6),
                "precision": round(float(precision_score(truth, predicted, zero_division=0)), 6),
                "recall": round(float(recall_score(truth, predicted, zero_division=0)), 6),
                "f1": round(float(f1_score(truth, predicted, zero_division=0)), 6),
            }, "note": "Requires independently observed, matured labels; synthetic retrospective measurement only."}
