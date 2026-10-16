"""Offline-only regression coverage for consolidated CP11-CP14 handoff."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

from mlops_platform.monitoring.metrics import summarize_requests, summarize_json_lines, percentile
from mlops_platform.monitoring.drift import population_stability_index, drift_report
from mlops_platform.monitoring.performance import evaluate_recent_predictions
from mlops_platform.deployment.release_gate import assess_candidate, BASELINE, LOCKED_MODEL_SHA256

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cp11_safety_flags_are_disabled():
    preflight = load_script("CP11_PREFLIGHT")
    assert all(preflight.gate_defaults_safe().values())


def test_cp11_template_not_approved():
    record = json.loads((ROOT / "CP9_RELEASE_APPROVAL_TEMPLATE.json").read_text(encoding="utf-8"))
    assert record["approved"] is False


def test_cp12_no_events_is_insufficient():
    x = summarize_requests([])
    assert x["status"] == "INSUFFICIENT_DATA" and x["request_count"] == 0


def test_cp12_counts_and_p95():
    items = [{"event":"http_request", "route":"/predict", "status_code":v, "duration_ms":10*i}
             for i,v in enumerate([200,401,503,200])]
    x=summarize_requests(items,minimum_requests=4)
    assert x["status"] == "MEASURED"
    assert x["request_count"] == 4 and x["error_count_5xx"] == 1 and x["unauthorized_401_count"] == 1
    assert x["p95_latency_ms"] == pytest.approx(28.5)


def test_cp12_no_payload_in_output():
    secret="super_private_untrusted_value"
    event={"event":"http_request", "route":"/predict", "status_code":200, "duration_ms":1,
           "request_body":secret, "X-API-Key":secret, "request_id":secret}
    assert secret not in json.dumps(summarize_requests([event], minimum_requests=1))


def test_cp12_skips_invalid_entries():
    result=summarize_json_lines(["not json", '{"hello": "world"}',
        '{"event":"http_request","route":"/predict","status_code":200,"duration_ms":2}'], 1)
    assert result["request_count"] == 1


def test_cp12_rejects_bad_percentile():
    with pytest.raises(ValueError):
        percentile([1,2], 110)


def test_cp13_identical_numeric_populations_zero():
    assert population_stability_index([1,2,3,4,5],[1,2,3,4,5]) == pytest.approx(0,abs=1e-12)


def test_cp13_identical_categorical_zero():
    assert population_stability_index(["A","B",None],["A","B",None],categorical=True) == pytest.approx(0,abs=1e-12)


def test_cp13_unseen_category_detected():
    assert population_stability_index(["A"]*50,["B"]*50,categorical=True) > 0.2


def test_cp13_empty_samples_rejected():
    with pytest.raises(ValueError):
        population_stability_index([], [1])


def test_cp13_reports_inconclusive_for_tiny_window():
    x=drift_report(pd.DataFrame({"a":[1,2],"b":["x","y"]}),
                   pd.DataFrame({"a":[1,3],"b":["x","z"]}),["a"],["b"])
    assert x["status"] == "INCONCLUSIVE" and set(x["features"]) == {"a","b"}


def test_cp13_rejects_duplicate_features():
    with pytest.raises(ValueError):
        drift_report(pd.DataFrame({"a":[1]}),pd.DataFrame({"a":[1]}),["a"],["a"])


def test_cp13_missing_labels_do_not_invent_metrics():
    assert evaluate_recent_predictions()["metrics"] is None


def test_cp13_few_labels_inconclusive():
    assert evaluate_recent_predictions([0,1],[0.1,0.9])["status"] == "INCONCLUSIVE"


def test_cp13_valid_delayed_metrics():
    obs=[0,1]*300
    prob=[0.2 if y else 0.05 for y in obs]
    val=evaluate_recent_predictions(obs,prob)
    assert val["status"] == "MEASURED" and val["metrics"]["roc_auc"]==1


def test_cp13_rejects_invalid_probabilities():
    with pytest.raises(ValueError):
        evaluate_recent_predictions([0,1],[0.2,float("nan")])


def valid_review(**overrides):
    args=dict(model_sha256=LOCKED_MODEL_SHA256, metrics=BASELINE, labeled_rows=507,
              parity_difference=1e-16, regression_tests_passed=True,
              security_review_passed=True, model_approval_record_present=True)
    args.update(overrides)
    return assess_candidate(**args)


def test_cp14_even_all_technical_evidence_cannot_promote():
    x=valid_review()
    assert x["status"] == "REVIEW_REQUIRED" and x["promotion_executed"] is False and x["registry_mutated"] is False


def test_cp14_missing_approval_blocked():
    assert "independent_release_approval_missing" in valid_review(model_approval_record_present=False)["blockers"]


def test_cp14_unknown_hash_blocked():
    assert "unknown_model_checksum" in valid_review(model_sha256="bad")["blockers"]


def test_cp14_bad_metrics_blocked():
    metrics=dict(BASELINE,roc_auc=0.3)
    assert "roc_auc_regression" in valid_review(metrics=metrics)["blockers"]


def test_cp14_insufficient_labeled_rows_blocked():
    assert "insufficient_labeled_evidence" in valid_review(labeled_rows=25)["blockers"]


def test_cp14_invalid_parity_blocked():
    assert "parity_failure" in valid_review(parity_difference=float("inf"))["blockers"]


def test_cp14_rollback_only_generates_instruction():
    x=load_script("CP14_ROLLBACK_PLAN").make_plan("demo", "api", "arn:aws:ecs:us-east-1:123456789012:task-definition/demo:1")
    assert x["executed"] is False and x["approved"] is False and "aws ecs update-service" in x["command_after_authorization"]


def test_cp14_rollback_bad_arn_rejected():
    with pytest.raises(ValueError):
        load_script("CP14_ROLLBACK_PLAN").make_plan("demo","api","bad")
