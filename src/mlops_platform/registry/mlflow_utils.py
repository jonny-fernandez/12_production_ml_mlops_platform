"""Project 12 CP4: register an already-validated CP3 candidate with local MLflow.

Uses the existing, completed CP4 experiment run. No retraining, cloud access,
model promotion, or calls to an LLM. Run from any working directory:

    python src/mlops_platform/registry/mlflow_utils.py --run-id <mlflow-run-id>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT.parent / "09_ai_attrition_prediction"
REGISTERED_NAME = "p09-attrition-gb"
TRACKING_URI = "sqlite:///mlflow_tracking.db"  # Same local URI used in CP4 steps 2-3.


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_candidate(run_sha: str) -> tuple[Path, dict]:
    candidates_root = ROOT / "artifacts" / "cp3_runs"
    if not candidates_root.is_dir():
        raise FileNotFoundError("CP3 candidate runs directory is missing")
    for directory in sorted(candidates_root.iterdir(), reverse=True):
        metadata_file = directory / "candidate_metadata.json"
        model_file = directory / "candidate_model_pipeline.joblib"
        if not (directory.is_dir() and metadata_file.is_file() and model_file.is_file()):
            continue
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if metadata.get("candidate_model_sha256") != run_sha:
            continue
        if sha256(model_file) != run_sha:
            raise ValueError("Candidate file does not match its locked SHA-256")
        return model_file, metadata
    raise FileNotFoundError("No local CP3 candidate matches the MLflow run SHA-256")


def verify_registered_model(version: str, features: list[str], threshold: float) -> float:
    """Compare registry-loaded probabilities with frozen Project 9 test evidence."""
    config = json.loads((SOURCE / "config/project_config.json").read_text(encoding="utf-8"))
    dataset = pd.read_csv(
        SOURCE / "data/raw/employee_attrition_snapshots_synthetic.csv",
        parse_dates=[config["date_column"]],
    )
    test = dataset.loc[dataset[config["date_column"]].between(
        config["test_start"], config["test_end"]
    )].copy()
    frozen = pd.read_csv(
        SOURCE / "outputs/final_test_predictions.csv",
        parse_dates=[config["date_column"]],
    )
    loaded = mlflow.sklearn.load_model(f"models:/{REGISTERED_NAME}/{version}")
    if list(loaded.feature_names_in_) != features:
        raise ValueError("Registered model feature order differs from CP3 metadata")
    replay = test[[config["id_column"], config["date_column"]]].copy()
    replay["registered_probability"] = loaded.predict_proba(test[features])[:, 1]
    joined = frozen.merge(
        replay, on=[config["id_column"], config["date_column"]], validate="one_to_one"
    )
    if len(test) != 507 or len(joined) != len(test) or len(frozen) != len(test):
        raise ValueError("Test record alignment failed")
    difference = float(np.max(np.abs(
        joined["registered_probability"].to_numpy()
        - joined["predicted_probability"].to_numpy()
    )))
    if difference > 1e-8:
        raise ValueError(f"Registered model failed probability parity: {difference}")
    if not np.array_equal(
        (joined["registered_probability"].to_numpy() >= threshold).astype(int),
        joined["predicted_class"].to_numpy(),
    ):
        raise ValueError("Registered model failed thresholded classification parity")
    return difference


def register_model(run_id: str) -> str:
    """Register the existing fitted pipeline as an MLflow sklearn-flavor model."""
    if Path.cwd().resolve() != ROOT.resolve():
        raise ValueError(f"Run this command from the Project 12 root: {ROOT}")
    if not (ROOT / "mlflow_tracking.db").is_file():
        raise FileNotFoundError("Local MLflow tracking database is missing")
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_registry_uri(TRACKING_URI)
    client = MlflowClient(tracking_uri=TRACKING_URI, registry_uri=TRACKING_URI)
    run = client.get_run(run_id)
    if run.info.status != "FINISHED":
        raise ValueError("Source MLflow experiment run is not finished")
    if run.data.tags.get("candidate_status") != "candidate_not_promoted":
        raise ValueError("Source MLflow candidate is not marked unpromoted")
    candidate_hash = run.data.tags.get("candidate_sha256")
    if not candidate_hash:
        raise ValueError("Source MLflow run does not contain the candidate checksum")
    candidate_path, metadata = find_candidate(candidate_hash)
    if metadata["status"] != "candidate_not_promoted":
        raise ValueError("CP3 candidate is not marked unpromoted")
    if metadata["synthetic_data_only"] is not True:
        raise ValueError("Only the documented synthetic dataset is permitted")
    if sha256(SOURCE / "artifacts/final_model_pipeline.joblib") != metadata["source_model_sha256"]:
        raise ValueError("Original model hash differs from CP3 metadata")
    features = metadata["feature_list"]
    threshold = float(metadata["operating_threshold"])
    if len(features) != 19 or threshold != 0.125:
        raise ValueError("Locked feature schema or threshold has changed")

    # Avoid accidentally producing duplicate registry versions on repeat executions.
    existing_names = {model.name for model in client.search_registered_models()}
    if REGISTERED_NAME in existing_names:
        versions = client.search_model_versions(f"name='{REGISTERED_NAME}'")
        for existing in versions:
            if (existing.tags.get("source_run_id") == run_id
                    and existing.tags.get("candidate_sha256") == candidate_hash):
                difference = verify_registered_model(str(existing.version), features, threshold)
                print("EXISTING VERSION FOUND; NO NEW VERSION CREATED")
                print(f"Registered model: {REGISTERED_NAME}")
                print(f"Version: {existing.version}")
                print(f"Run ID: {run_id}")
                print(f"Prediction parity max difference: {difference:.3e}")
                print("Candidate status: candidate_not_promoted")
                print("RESULT: MLFLOW MODEL REGISTRY PASSED")
                return str(existing.version)

    model = joblib.load(candidate_path)  # Trusted file created locally in CP3.
    if list(model.feature_names_in_) != features:
        raise ValueError("Candidate pipeline does not match the locked feature order")
    df = pd.read_csv(SOURCE / "data/raw/employee_attrition_snapshots_synthetic.csv")
    example = df[features].head(3).copy()
    signature = infer_signature(example, model.predict_proba(example))

    # The CP4 run previously stored a raw .joblib artifact. The model registry
    # requires a proper MLflow model package containing MLmodel metadata.
    # Package the same fitted pipeline; do not fit or change its parameters.
    with mlflow.start_run(run_id=run_id):
        logged_info = mlflow.sklearn.log_model(
            sk_model=model,
            name="attrition_probability_pipeline",
            signature=signature,
            input_example=example,
            pyfunc_predict_fn="predict_proba",
            serialization_format="cloudpickle",
            registered_model_name=REGISTERED_NAME,
            await_registration_for=120,
            metadata={
                "source_project": "09_ai_attrition_prediction",
                "candidate_sha256": candidate_hash,
                "operating_threshold": threshold,
                "synthetic_data_only": True,
                "candidate_status": "candidate_not_promoted",
            },
        )

    version = getattr(logged_info, "registered_model_version", None)
    if version is None:
        raise RuntimeError("MLflow did not return a registered model version")
    version = str(version)
    client.set_model_version_tag(REGISTERED_NAME, version, "source_run_id", run_id)
    client.set_model_version_tag(REGISTERED_NAME, version, "candidate_sha256", candidate_hash)
    client.set_model_version_tag(REGISTERED_NAME, version, "candidate_status", "candidate_not_promoted")
    client.set_model_version_tag(REGISTERED_NAME, version, "operating_threshold", str(threshold))
    client.set_model_version_tag(REGISTERED_NAME, version, "synthetic_data_only", "true")
    difference = verify_registered_model(version, features, threshold)
    registered = client.get_model_version(REGISTERED_NAME, version)
    if registered.tags.get("candidate_status") != "candidate_not_promoted":
        raise ValueError("Registry version was not tagged as unpromoted")
    print("\nPROJECT 12 - CP4 MODEL REGISTRY")
    print("=" * 44)
    print("Registered model:", REGISTERED_NAME)
    print("Version:", version)
    print("Source MLflow run:", run_id)
    print("Status:", registered.status)
    print("Candidate status:", registered.tags["candidate_status"])
    print("Original candidate SHA-256:", candidate_hash)
    print("Operating threshold:", threshold)
    print("Registered-model probability max difference:", f"{difference:.3e}")
    print("MLflow URI:", f"models:/{REGISTERED_NAME}/{version}")
    print("RESULT: MLFLOW MODEL REGISTRY PASSED")
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Completed CP4 MLflow experiment run ID")
    args = parser.parse_args()
    register_model(args.run_id)


if __name__ == "__main__":
    main()
