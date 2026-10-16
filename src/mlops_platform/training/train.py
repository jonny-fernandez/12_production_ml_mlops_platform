"""Project 12 CP3: reproduce the validated Project 9 training specification.

Default mode only inspects the source files. Use --train explicitly to fit a
separate candidate in Project 12 after source-contract checks pass.
The original Project 9 files are never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

PROJECT12_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = PROJECT12_ROOT.parent / "09_ai_attrition_prediction"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_source(source: Path) -> dict:
    """Validate provenance, the locked decision, and chronological data splits."""
    source = source.resolve()
    paths = {
        "config": source / "config/project_config.json",
        "lock": source / "artifacts/development_model_lock.json",
        "metadata": source / "artifacts/model_metadata.json",
        "model": source / "artifacts/final_model_pipeline.joblib",
        "data": source / "data/raw/employee_attrition_snapshots_synthetic.csv",
        "predictions": source / "outputs/final_test_predictions.csv",
    }
    absent = [name for name, path in paths.items() if not path.is_file()]
    if absent:
        raise FileNotFoundError(f"Missing Project 9 files: {absent}")

    cfg = read_json(paths["config"])
    lock = read_json(paths["lock"])
    meta = read_json(paths["metadata"])

    if cfg.get("synthetic_data_only") is not True or meta.get("synthetic_data_only") is not True:
        raise ValueError("CP3 requires the original synthetic dataset only")
    if lock.get("status") != "LOCKED_BEFORE_FINAL_TEST":
        raise ValueError("Source model selection must be locked before final test")
    if lock.get("test_used_for_selection") is not False:
        raise ValueError("Source test set must not have been used for selection")
    if lock.get("model_name") != "GradientBoostingClassifier":
        raise ValueError("Unexpected locked model type")
    if lock.get("random_seed") != cfg.get("random_seed") or cfg["random_seed"] != meta["random_seed"]:
        raise ValueError("Training seeds disagree")
    if float(lock["operating_threshold"]) != float(meta["operating_threshold"]):
        raise ValueError("Locked threshold and metadata disagree")
    if sha256_file(paths["model"]) != meta["model_sha256"]:
        raise ValueError("Project 9 model SHA-256 mismatch")

    df = pd.read_csv(paths["data"], parse_dates=[cfg["date_column"]])
    features = list(meta["feature_list"])
    excluded = list(meta["excluded_feature_list"])
    if len(features) != 19 or len(set(features)) != 19:
        raise ValueError("Expected 19 unique locked features")
    if list(df.columns) != [*features, *excluded]:
        # Column position is not necessarily grouped. Verify original order
        # relative to features and excluded columns instead.
        actual_features = [name for name in df.columns if name not in excluded]
        actual_excluded = [name for name in df.columns if name in excluded]
        if actual_features != features or actual_excluded != excluded:
            raise ValueError("Dataset columns do not match locked metadata")
    if df.empty or df[cfg["id_column"]].duplicated().any():
        raise ValueError("Source data is empty or employee identifiers repeat")
    if df[features].isnull().any().any():
        raise ValueError("Unexpected missing model feature values in original dataset")
    if not df[cfg["target"]].isin([0, 1]).all():
        raise ValueError("Expected binary target with no missing values")

    dates = df[cfg["date_column"]]
    train = df.loc[dates <= pd.Timestamp(cfg["train_end"])].copy()
    validation = df.loc[dates.between(cfg["validation_start"], cfg["validation_end"])].copy()
    test = df.loc[dates.between(cfg["test_start"], cfg["test_end"])].copy()
    splits = {"train": train, "validation": validation, "test": test}
    for name, frame in splits.items():
        if frame.empty or len(frame) != meta["splits"][name]["rows"]:
            raise ValueError(f"{name} split does not match recorded source metadata")
    if not (train[cfg["date_column"]].max() < validation[cfg["date_column"]].min()
            < test[cfg["date_column"]].min()):
        raise ValueError("Chronological windows overlap or are unordered")
    if sum(len(frame) for frame in splits.values()) != len(df):
        raise ValueError("Dataset has rows outside locked training/validation/test windows")

    categorical = train[features].select_dtypes(include="object").columns.tolist()
    numeric = [name for name in features if name not in categorical]
    if len(categorical) != 5 or len(numeric) != 14:
        raise ValueError("Expected 5 categorical and 14 numeric input features")
    if not all(pd.api.types.is_numeric_dtype(train[name]) for name in numeric):
        raise ValueError("Numeric feature dtype mismatch")

    return {
        "source": source, "paths": paths, "config": cfg, "lock": lock,
        "metadata": meta, "train": train, "validation": validation,
        "test": test, "features": features, "categorical": categorical,
        "numeric": numeric,
    }


def build_pipeline(numeric: list[str], categorical: list[str], seed: int) -> Pipeline:
    """Reproduce Project 9's exact architecture; no tuning or refitting on test."""
    return Pipeline(steps=[
        ("preprocessor", ColumnTransformer(
            transformers=[
                ("num", Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))]), numeric),
                ("cat", Pipeline(steps=[
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]), categorical),
            ], sparse_threshold=0,
        )),
        ("model", GradientBoostingClassifier(random_state=seed)),
    ])


def check_prediction_parity(pipeline: Pipeline, context: dict) -> float:
    """Compare fresh predictions with already-frozen final-test evidence."""
    cfg = context["config"]
    test = context["test"]
    saved = pd.read_csv(context["paths"]["predictions"], parse_dates=[cfg["date_column"]])
    replay = test[[cfg["id_column"], cfg["date_column"], cfg["target"]]].copy()
    replay["candidate_probability"] = pipeline.predict_proba(test[context["features"]])[:, 1]
    merged = saved.merge(replay, on=[cfg["id_column"], cfg["date_column"]], validate="one_to_one")
    if len(merged) != len(saved) or len(merged) != len(test):
        raise ValueError("Saved and fresh prediction keys differ")
    if not np.array_equal(merged["actual_target"].to_numpy(), merged[cfg["target"]].to_numpy()):
        raise ValueError("Final-test target labels differ")
    maximum_difference = float(np.max(np.abs(
        merged["candidate_probability"].to_numpy()
        - merged["predicted_probability"].to_numpy()
    )))
    if maximum_difference > 1e-8:
        raise ValueError(f"Freshly trained model failed probability parity: {maximum_difference}")
    threshold = float(context["lock"]["operating_threshold"])
    predicted_classes = (merged["candidate_probability"].to_numpy() >= threshold).astype(int)
    if not np.array_equal(predicted_classes, merged["predicted_class"].to_numpy()):
        raise ValueError("Freshly trained model failed class parity")
    return maximum_difference


def train(source: Path = DEFAULT_SOURCE, output_dir: Path | None = None) -> dict:
    """Train and verify an isolated candidate; never modify original Project 9."""
    context = verify_source(source)
    cfg = context["config"]
    features = context["features"]
    train_data = context["train"]
    pipeline = build_pipeline(context["numeric"], context["categorical"], cfg["random_seed"])
    pipeline.fit(train_data[features], train_data[cfg["target"]])

    if list(pipeline.feature_names_in_) != features:
        raise ValueError("Trained model feature order mismatch")
    if pipeline.named_steps["model"].get_params() != context["metadata"]["model_parameters"]:
        raise ValueError("Trained estimator hyperparameters differ from locked source")
    max_difference = check_prediction_parity(pipeline, context)

    if output_dir is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output_dir = PROJECT12_ROOT / "artifacts" / "cp3_runs" / stamp
    output_dir = output_dir.resolve()
    if output_dir == context["source"] or context["source"] in output_dir.parents:
        raise ValueError("Output directory must not be inside Project 9")
    output_dir.mkdir(parents=True, exist_ok=False)  # Never overwrite a prior run.
    model_path = output_dir / "candidate_model_pipeline.joblib"
    joblib.dump(pipeline, model_path)

    run_metadata = {
        "project": "12_production_ml_mlops_platform",
        "checkpoint": "CP3",
        "status": "candidate_not_promoted",
        "source_project": "09_ai_attrition_prediction",
        "source_model_sha256": context["metadata"]["model_sha256"],
        "source_data_sha256": sha256_file(context["paths"]["data"]),
        "source_config_sha256": sha256_file(context["paths"]["config"]),
        "source_lock_sha256": sha256_file(context["paths"]["lock"]),
        "candidate_model_sha256": sha256_file(model_path),
        "model_name": "GradientBoostingClassifier",
        "operating_threshold": float(context["lock"]["operating_threshold"]),
        "threshold_selected_on": "Project 9 validation split (locked)",
        "model_parameters": pipeline.named_steps["model"].get_params(),
        "feature_list": features,
        "numeric_features": context["numeric"],
        "categorical_features": context["categorical"],
        "target": cfg["target"],
        "prediction_horizon_days": cfg["prediction_horizon_days"],
        "random_seed": cfg["random_seed"],
        "train_rows": len(context["train"]),
        "validation_rows": len(context["validation"]),
        "test_rows": len(context["test"]),
        "maximum_test_probability_difference": max_difference,
        "prediction_parity_tolerance": 1e-8,
        "test_used_for_model_selection": False,
        "synthetic_data_only": True,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scikit_learn_version": sklearn.__version__,
        "joblib_version": joblib.__version__,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    metadata_path = output_dir / "candidate_metadata.json"
    metadata_path.write_text(json.dumps(run_metadata, indent=2), encoding="utf-8")
    print(f"CANDIDATE SAVED: {model_path}")
    print(f"METADATA SAVED:  {metadata_path}")
    print(f"Maximum probability difference: {max_difference:.3e}")
    return run_metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-project", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--train", action="store_true", help="Explicitly train and save an isolated candidate")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.train:
        train(args.source_project, args.output_dir)
    else:
        context = verify_source(args.source_project)
        print("CP3 SOURCE VALIDATION: PASS (read-only)")
        print(f"Source project: {context['source']}")
        print(f"Source model SHA-256: {context['metadata']['model_sha256']}")
        print(f"Training rows: {len(context['train'])}")
        print(f"Validation rows: {len(context['validation'])}")
        print(f"Test rows: {len(context['test'])}")
        print(f"Features: {len(context['features'])} ({len(context['numeric'])} numeric, {len(context['categorical'])} categorical)")
        print(f"Locked threshold: {context['lock']['operating_threshold']}")
        print("No model fitted; no files written.")


if __name__ == "__main__":
    main()
