"""Read-only candidate-screening rehearsal. NEVER promotes or modifies a registry."""
from __future__ import annotations
import json
from pathlib import Path
from sys import path as search_path

ROOT = Path(__file__).resolve().parent
search_path.insert(0, str(ROOT / "src"))
from mlops_platform.deployment.release_gate import assess_candidate, LOCKED_MODEL_SHA256


def main():
    source = ROOT.parent / "09_ai_attrition_prediction"
    metrics = json.loads((source / "outputs/final_test_metrics.json").read_text(encoding="utf-8"))
    result = assess_candidate(
        model_sha256=LOCKED_MODEL_SHA256,
        metrics=metrics, labeled_rows=507, parity_difference=1.11e-16,
        regression_tests_passed=True, security_review_passed=False,
        model_approval_record_present=False,
    )
    target = ROOT / "outputs" / "cp14_release_review.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("PROJECT 12 — CP14 READ-ONLY PROMOTION GATE")
    print("Status:", result["status"], "Blockers:", ", ".join(result["blockers"]))
    print("Registry mutated:", result["registry_mutated"], "Promotion executed:", result["promotion_executed"])
    print("Report:", target)
    print("RESULT: CP14 GATE EVALUATED — PROMOTION NOT AUTHORIZED")


if __name__ == "__main__":
    main()
