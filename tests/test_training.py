"""CP3 regression tests for reproducible training and artifact provenance.

Unit tests are self-contained, so GitHub Actions does not need Project 9.
Optional integration tests run when the trusted sibling Project 9 source exists.
No network calls, paid APIs, cloud operations, or writes to Project 9.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import GradientBoostingClassifier

training = importlib.import_module("mlops_platform.training.train")

PROJECT12_ROOT = Path(__file__).resolve().parents[1]
PROJECT9_ROOT = PROJECT12_ROOT.parent / "09_ai_attrition_prediction"

NUMERIC = [
    "age", "tenure_months", "monthly_salary_annualized", "overtime_hours_90d",
    "absences_90d", "performance_score", "engagement_score", "manager_changes_12m",
    "months_since_promotion", "commute_minutes", "training_hours_12m",
    "remote_work_ratio", "salary_change_pct_12m", "internal_moves_24m",
]
CATEGORICAL = ["department", "job_family", "job_level", "location", "employment_type"]
FEATURES = NUMERIC + CATEGORICAL
TARGET = "attrition_within_90_days"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


@pytest.fixture
def minimal_source(tmp_path: Path) -> Path:
    """Build synthetic, independent source files for contract/failure tests."""
    root = tmp_path / "synthetic_p09"
    model_path = root / "artifacts/final_model_pipeline.joblib"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"TEST MODEL BYTES - NOT A PICKLE")
    model_digest = hashlib.sha256(model_path.read_bytes()).hexdigest()

    cfg = {
        "synthetic_data_only": True,
        "random_seed": 42,
        "date_column": "snapshot_date",
        "id_column": "employee_id",
        "target": TARGET,
        "train_end": "2025-06-30",
        "validation_start": "2025-07-01",
        "validation_end": "2025-07-31",
        "test_start": "2025-08-01",
        "test_end": "2025-08-31",
    }
    lock = {
        "status": "LOCKED_BEFORE_FINAL_TEST",
        "test_used_for_selection": False,
        "model_name": "GradientBoostingClassifier",
        "random_seed": 42,
        "operating_threshold": 0.125,
    }
    meta = {
        "synthetic_data_only": True,
        "random_seed": 42,
        "operating_threshold": 0.125,
        "model_sha256": model_digest,
        "feature_list": FEATURES,
        "excluded_feature_list": ["employee_id", "snapshot_date", TARGET],
        "splits": {name: {"rows": 2} for name in ("train", "validation", "test")},
    }
    _write_json(root / "config/project_config.json", cfg)
    _write_json(root / "artifacts/development_model_lock.json", lock)
    _write_json(root / "artifacts/model_metadata.json", meta)

    rows = []
    for i, date in enumerate(
        ["2025-06-01", "2025-06-02", "2025-07-01", "2025-07-02", "2025-08-01", "2025-08-02"]
    ):
        row = {name: float(i + j + 1) for j, name in enumerate(NUMERIC)}
        row.update({name: f"category_{i % 2}" for name in CATEGORICAL})
        row.update({"employee_id": f"TEST_{i}", "snapshot_date": date, TARGET: i % 2})
        rows.append(row)
    df = pd.DataFrame(rows, columns=FEATURES + ["employee_id", "snapshot_date", TARGET])
    path = root / "data/raw/employee_attrition_snapshots_synthetic.csv"
    path.parent.mkdir(parents=True)
    df.to_csv(path, index=False)

    # Presence is enough for verify_source. A later unit test supplies valid saved predictions.
    pred_path = root / "outputs/final_test_predictions.csv"
    pred_path.parent.mkdir(parents=True)
    pd.DataFrame([{"employee_id": "TEST_4"}, {"employee_id": "TEST_5"}]).to_csv(pred_path, index=False)
    return root


def test_sha256_file_known_content(tmp_path: Path) -> None:
    path = tmp_path / "example.bin"
    path.write_bytes(b"known test content")
    assert training.sha256_file(path) == hashlib.sha256(b"known test content").hexdigest()


def test_preflight_checks_schema_and_chronology(minimal_source: Path) -> None:
    context = training.verify_source(minimal_source)
    assert [len(context[name]) for name in ("train", "validation", "test")] == [2, 2, 2]
    assert len(context["features"]) == 19
    assert len(context["numeric"]) == 14
    assert len(context["categorical"]) == 5
    assert set(context["features"]) == set(context["numeric"] + context["categorical"])


def test_preflight_rejects_modified_source_model(minimal_source: Path) -> None:
    (minimal_source / "artifacts/final_model_pipeline.joblib").write_bytes(b"TAMPERED")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        training.verify_source(minimal_source)


def test_preflight_rejects_test_set_selection(minimal_source: Path) -> None:
    path = minimal_source / "artifacts/development_model_lock.json"
    lock = training.read_json(path)
    lock["test_used_for_selection"] = True
    _write_json(path, lock)
    with pytest.raises(ValueError, match="must not have been used for selection"):
        training.verify_source(minimal_source)


def test_preflight_rejects_missing_files(minimal_source: Path) -> None:
    (minimal_source / "artifacts/development_model_lock.json").unlink()
    with pytest.raises(FileNotFoundError, match="Missing Project 9 files"):
        training.verify_source(minimal_source)


def test_preflight_rejects_overlapping_windows(minimal_source: Path) -> None:
    path = minimal_source / "config/project_config.json"
    cfg = training.read_json(path)
    cfg["validation_start"] = "2025-06-02"
    cfg["validation_end"] = "2025-07-01"
    _write_json(path, cfg)
    with pytest.raises(ValueError, match="Chronological windows overlap"):
        training.verify_source(minimal_source)


def test_pipeline_trains_with_locked_feature_schema() -> None:
    n = 30
    values = {
        name: np.arange(n, dtype=float) * (j + 1) + 1
        for j, name in enumerate(NUMERIC)
    }
    values.update({name: ["A" if i % 2 else "B" for i in range(n)] for name in CATEGORICAL})
    frame = pd.DataFrame(values, columns=FEATURES)
    labels = np.array([i % 2 for i in range(n)])

    pipeline = training.build_pipeline(NUMERIC, CATEGORICAL, seed=42)
    assert isinstance(pipeline.named_steps["model"], GradientBoostingClassifier)
    assert pipeline.named_steps["model"].random_state == 42
    pipeline.fit(frame, labels)
    assert (pipeline.named_steps["preprocessor"]
            .named_transformers_["cat"].named_steps["onehot"].handle_unknown == "ignore")
    probability = pipeline.predict_proba(frame.iloc[:4])
    assert list(pipeline.feature_names_in_) == FEATURES
    assert probability.shape == (4, 2)
    assert np.isfinite(probability).all()
    assert np.allclose(probability.sum(axis=1), 1.0)


class _FixedProbabilities:
    def __init__(self, p: list[float]):
        self.p = np.asarray(p, dtype=float)

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        assert len(frame) == len(self.p)
        return np.column_stack([1.0 - self.p, self.p])


def _parity_context(source: Path) -> dict:
    context = training.verify_source(source)
    test = context["test"]
    cfg = context["config"]
    saved = test[[cfg["id_column"], cfg["date_column"]]].copy()
    saved["actual_target"] = test[cfg["target"]].to_numpy()
    saved["predicted_probability"] = [0.05, 0.8]
    saved["predicted_class"] = [0, 1]
    saved.to_csv(context["paths"]["predictions"], index=False)
    return context


def test_prediction_parity_passes_exact_probabilities(minimal_source: Path) -> None:
    context = _parity_context(minimal_source)
    assert training.check_prediction_parity(_FixedProbabilities([0.05, 0.8]), context) == 0.0


def test_prediction_parity_rejects_probability_drift(minimal_source: Path) -> None:
    context = _parity_context(minimal_source)
    with pytest.raises(ValueError, match="probability parity"):
        training.check_prediction_parity(_FixedProbabilities([0.05, 0.9]), context)


def test_prediction_parity_rejects_class_mismatch(minimal_source: Path) -> None:
    context = _parity_context(minimal_source)
    # 0.10 differs but tolerance would catch that first. Override comparator
    # with an inconsistent recorded class to isolate the class-parity gate.
    path = context["paths"]["predictions"]
    df = pd.read_csv(path)
    df.loc[0, "predicted_class"] = 1
    df.to_csv(path, index=False)
    with pytest.raises(ValueError, match="class parity"):
        training.check_prediction_parity(_FixedProbabilities([0.05, 0.8]), context)


def test_prediction_parity_rejects_mismatched_targets(minimal_source: Path) -> None:
    context = _parity_context(minimal_source)
    path = context["paths"]["predictions"]
    df = pd.read_csv(path)
    df.loc[0, "actual_target"] = 1 - int(df.loc[0, "actual_target"])
    df.to_csv(path, index=False)
    with pytest.raises(ValueError, match="target labels differ"):
        training.check_prediction_parity(_FixedProbabilities([0.05, 0.8]), context)


def _real_source_available() -> bool:
    return (PROJECT9_ROOT / "artifacts/final_model_pipeline.joblib").is_file()


@pytest.mark.skipif(not _real_source_available(), reason="Optional integration: sibling Project 9 not present")
def test_real_source_validates_without_modification() -> None:
    context = training.verify_source(PROJECT9_ROOT)
    assert len(context["train"]) == 1997
    assert len(context["validation"]) == 496
    assert len(context["test"]) == 507
    assert context["metadata"]["model_sha256"] == training.sha256_file(context["paths"]["model"])


@pytest.mark.skipif(not _real_source_available(), reason="Optional integration: sibling Project 9 not present")
def test_retraining_writes_isolated_candidate_with_valid_metadata(tmp_path: Path) -> None:
    output = tmp_path / "isolated_cp3_candidate"
    before_hash = training.sha256_file(PROJECT9_ROOT / "artifacts/final_model_pipeline.joblib")

    metadata = training.train(source=PROJECT9_ROOT, output_dir=output)
    artifact = output / "candidate_model_pipeline.joblib"
    record = json.loads((output / "candidate_metadata.json").read_text(encoding="utf-8"))
    pipeline = joblib.load(artifact)  # Produced locally by this test.

    assert metadata == record
    assert record["candidate_model_sha256"] == training.sha256_file(artifact)
    assert record["source_model_sha256"] == before_hash
    assert training.sha256_file(PROJECT9_ROOT / "artifacts/final_model_pipeline.joblib") == before_hash
    assert record["status"] == "candidate_not_promoted"
    assert record["operating_threshold"] == 0.125
    assert record["test_used_for_model_selection"] is False
    assert record["maximum_test_probability_difference"] <= 1e-8
    assert record["train_rows"] == 1997
    assert record["validation_rows"] == 496
    assert record["test_rows"] == 507
    assert list(pipeline.feature_names_in_) == record["feature_list"]

    # Creating another run with an existing output directory must fail safely.
    with pytest.raises(FileExistsError):
        training.train(source=PROJECT9_ROOT, output_dir=output)
