"""CP14 deterministic technical promotion screening (never auto-approval)."""
from __future__ import annotations
from typing import Mapping
import math

LOCKED_MODEL_SHA256 = "27585a4b8443be29a7cf41a5a2bfd3227ae4a66d8dd947afd88d38111f404d43"
BASELINE = {"roc_auc": 0.6156236323851203, "pr_auc": 0.19942038019456926,
            "brier_score": 0.08718630417497854}


def assess_candidate(*, model_sha256: str, metrics: Mapping[str, float] | None,
                     labeled_rows: int, parity_difference: float,
                     regression_tests_passed: bool, security_review_passed: bool,
                     model_approval_record_present: bool = False) -> dict:
    """Return review blockers. An approval record does NOT automatically promote."""
    blockers = []
    if model_sha256 != LOCKED_MODEL_SHA256:
        blockers.append("unknown_model_checksum")
    if labeled_rows < 500:
        blockers.append("insufficient_labeled_evidence")
    if type(parity_difference) not in (int, float) or not math.isfinite(parity_difference) or not 0 <= parity_difference <= 1e-8:
        blockers.append("parity_failure")
    if not regression_tests_passed:
        blockers.append("regression_suite_failed")
    if not security_review_passed:
        blockers.append("security_review_missing_or_failed")
    if metrics is None or any(k not in metrics or type(metrics[k]) not in (int, float) or not math.isfinite(metrics[k]) for k in BASELINE):
        blockers.append("missing_verified_metrics")
    else:
        if metrics["roc_auc"] < BASELINE["roc_auc"] - 0.02:
            blockers.append("roc_auc_regression")
        if metrics["pr_auc"] < BASELINE["pr_auc"] - 0.02:
            blockers.append("pr_auc_regression")
        if metrics["brier_score"] > BASELINE["brier_score"] + 0.02:
            blockers.append("brier_regression")
    if not model_approval_record_present:
        blockers.append("independent_release_approval_missing")
    return {"format": "project12_cp14_candidate_gate_v1", "status": "BLOCKED" if blockers else "REVIEW_REQUIRED",
            "promotion_executed": False, "registry_mutated": False, "blockers": blockers,
            "note": "Technical screening does not authorize model use, promotion, or any AWS deployment."}
