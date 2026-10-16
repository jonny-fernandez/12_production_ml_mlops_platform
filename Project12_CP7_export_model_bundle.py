"""Project 12 CP7: export a verified local-only model bundle for Docker.

Run from the Project 12 repository root:

    .\\.venv\\Scripts\\python.exe .\\Project12_CP7_export_model_bundle.py

The registered MLflow version and the original Project 9 files are READ ONLY.
Exports a single verified joblib model plus a provenance manifest to
artifacts/cp7_container_model, for a future read-only Compose bind mount.
Does not build/start Docker, retrain, register, or promote a model.

SECURITY: joblib uses pickle serialization. Only load the locally trained model
whose SHA-256 matches the pinned CP3 checksum. Never load untrusted joblib.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.tracking import MlflowClient


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "09_ai_attrition_prediction"
REGISTERED_NAME = "p09-attrition-gb"
REGISTERED_VERSION = "1"
RUN_ID = "0a2731b4c9c64abfb373166e22b1f97e"
THRESHOLD = 0.125
CANDIDATE_SHA = "27585a4b8443be29a7cf41a5a2bfd3227ae4a66d8dd947afd88d38111f404d43"
SOURCE_SHA = "12f9c529ecaffe70f8c1ad401ab398e25b135d8a5ecab6edd71584d65a126755"
ARTIFACT_NAME = "candidate_model_pipeline.joblib"
MANIFEST_NAME = "model_bundle_manifest.json"
OUTPUT = ROOT / "artifacts" / "cp7_container_model"
TOLERANCE = 1e-8


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def locate_candidate() -> tuple[Path, dict]:
    runs = ROOT / "artifacts" / "cp3_runs"
    require(runs.is_dir(), "Missing CP3 candidate runs folder")
    for folder in sorted(runs.iterdir(), reverse=True):
        model_file = folder / ARTIFACT_NAME
        metadata_file = folder / "candidate_metadata.json"
        if not folder.is_dir() or not model_file.is_file() or not metadata_file.is_file():
            continue
        metadata = read_json(metadata_file)
        if metadata.get("candidate_model_sha256") != CANDIDATE_SHA:
            continue
        require(checksum(model_file) == CANDIDATE_SHA, "CP3 model checksum mismatch")
        require(metadata.get("status") == "candidate_not_promoted", "CP3 status changed")
        require(metadata.get("synthetic_data_only") is True, "Not synthetic-only candidate")
        require(metadata.get("source_model_sha256") == SOURCE_SHA, "Source checksum in CP3 metadata changed")
        require(float(metadata.get("operating_threshold", -1)) == THRESHOLD, "CP3 threshold changed")
        return model_file, metadata
    raise FileNotFoundError("No verified CP3 candidate matched the pinned SHA-256")


def validate_registry():
    db = ROOT / "mlflow_tracking.db"
    require(db.is_file(), "Local MLflow tracking database does not exist")
    uri = "sqlite:///mlflow_tracking.db"
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    client = MlflowClient(tracking_uri=uri, registry_uri=uri)
    version = client.get_model_version(REGISTERED_NAME, REGISTERED_VERSION)
    require(version.status == "READY", "Registry model version is not READY")
    tags = version.tags
    require(tags.get("source_run_id") == RUN_ID, "Registry source run differs from CP4")
    require(tags.get("candidate_sha256") == CANDIDATE_SHA, "Registry source checksum differs")
    require(tags.get("candidate_status") == "candidate_not_promoted", "Registry status changed")
    require(tags.get("synthetic_data_only") == "true", "Registry model is not synthetic-only")
    require(float(tags.get("operating_threshold", -1)) == THRESHOLD, "Registry threshold changed")
    run = client.get_run(RUN_ID)
    require(run.info.status == "FINISHED", "CP4 MLflow run is not finished")
    require(run.data.tags.get("candidate_sha256") == CANDIDATE_SHA, "CP4 run source SHA mismatch")
    require(run.data.tags.get("candidate_status") == "candidate_not_promoted", "CP4 run approval status changed")
    return mlflow.sklearn.load_model(f"models:/{REGISTERED_NAME}/{REGISTERED_VERSION}")


def validate_prediction_parity(candidate_model, registry_model, metadata: dict) -> tuple[float, float, int]:
    cfg = read_json(SOURCE / "config" / "project_config.json")
    source_metadata = read_json(SOURCE / "artifacts" / "model_metadata.json")
    source_model = SOURCE / "artifacts" / "final_model_pipeline.joblib"
    require(checksum(source_model) == SOURCE_SHA, "Original Project 9 model checksum changed")
    require(source_metadata.get("model_sha256") == SOURCE_SHA, "Original Project 9 metadata differs")
    require(cfg.get("synthetic_data_only") is True, "Source data is not synthetic-only")

    features = list(source_metadata["feature_list"])
    require(len(features) == 19, "Expected exactly 19 source features")
    require(features == list(metadata["feature_list"]), "CP3 and Project 9 features differ")
    for name, model in (("CP3", candidate_model), ("MLflow", registry_model)):
        require(list(model.feature_names_in_) == features, f"{name} feature order differs")
        require(tuple(int(x) for x in model.classes_) == (0, 1), f"{name} class labels differ")

    data = pd.read_csv(
        SOURCE / "data/raw/employee_attrition_snapshots_synthetic.csv",
        parse_dates=[cfg["date_column"]],
    )
    test = data.loc[
        data[cfg["date_column"]].between(cfg["test_start"], cfg["test_end"])
    ].copy()
    saved = pd.read_csv(
        SOURCE / "outputs/final_test_predictions.csv",
        parse_dates=[cfg["date_column"]],
    )
    keys = [cfg["id_column"], cfg["date_column"]]
    require(len(test) == len(saved) == 507, "Frozen test record count changed")
    require(not saved.duplicated(keys).any(), "Duplicate frozen test keys")
    require(not test.duplicated(keys).any(), "Duplicate source test keys")
    aligned = test[keys + [cfg["target"]]].merge(
        saved, on=keys, validate="one_to_one", sort=False,
    )
    require(len(aligned) == 507, "Frozen test record alignment failed")
    require(
        np.array_equal(aligned[cfg["target"]].to_numpy(), aligned["actual_target"].to_numpy()),
        "Source test outcome labels differ",
    )

    # Align the feature matrix to the persisted record keys before comparing.
    input_frame = aligned[keys].merge(test[keys + features], on=keys, validate="one_to_one", sort=False)
    require(len(input_frame) == 507, "Feature matrix alignment failed")
    frozen_probs = aligned["predicted_probability"].to_numpy(dtype=float)
    cp3_probs = candidate_model.predict_proba(input_frame[features])[:, 1]
    mlflow_probs = registry_model.predict_proba(input_frame[features])[:, 1]
    require(np.isfinite(cp3_probs).all() and np.isfinite(mlflow_probs).all(), "Nonfinite predictions")
    candidate_diff = float(np.max(np.abs(cp3_probs - frozen_probs)))
    registry_diff = float(np.max(np.abs(mlflow_probs - frozen_probs)))
    require(candidate_diff <= TOLERANCE, "CP3 candidate failed frozen prediction parity")
    require(registry_diff <= TOLERANCE, "MLflow model failed frozen prediction parity")
    frozen_labels = aligned["predicted_class"].to_numpy(dtype=int)
    require(np.array_equal((cp3_probs >= THRESHOLD).astype(int), frozen_labels), "CP3 classes differ")
    require(np.array_equal((mlflow_probs >= THRESHOLD).astype(int), frozen_labels), "MLflow classes differ")
    return candidate_diff, registry_diff, len(aligned)


def export_bundle(candidate_file: Path, metadata: dict, candidate_diff: float,
                  registry_diff: float, rows: int) -> str:
    manifest = {
        "format": "project12_verified_local_joblib_v1",
        "model_name": REGISTERED_NAME,
        "model_version": REGISTERED_VERSION,
        "source_mlflow_run_id": RUN_ID,
        "candidate_status": "candidate_not_promoted",
        "synthetic_data_only": True,
        "operating_threshold": THRESHOLD,
        "candidate_model_sha256": CANDIDATE_SHA,
        "source_model_sha256": SOURCE_SHA,
        "model_filename": ARTIFACT_NAME,
        "feature_list": metadata["feature_list"],
        "test_records": rows,
        "candidate_frozen_max_difference": candidate_diff,
        "registry_frozen_max_difference": registry_diff,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    if OUTPUT.exists():
        require(OUTPUT.is_dir(), "Bundle destination exists but is not a folder")
        model_file = OUTPUT / ARTIFACT_NAME
        manifest_file = OUTPUT / MANIFEST_NAME
        require(model_file.is_file() and manifest_file.is_file(), "Existing bundle is incomplete; refusing overwrite")
        require(checksum(model_file) == CANDIDATE_SHA, "Existing bundle model checksum mismatch")
        previous = read_json(manifest_file)
        for key, value in manifest.items():
            if key != "generated_utc":
                require(previous.get(key) == value, f"Existing bundle manifest differs: {key}")
        return "VERIFIED EXISTING BUNDLE; NO FILES OVERWRITTEN"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".cp7_bundle_staging_", dir=OUTPUT.parent))
    try:
        staged_model = temporary / ARTIFACT_NAME
        shutil.copy2(candidate_file, staged_model)
        require(checksum(staged_model) == CANDIDATE_SHA, "Exported copy SHA-256 mismatch")
        (temporary / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary.rename(OUTPUT)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return "NEW BUNDLE CREATED"


def main() -> None:
    require(Path.cwd().resolve() == ROOT.resolve(), "Run from Project 12 repository root")
    require((ROOT / "requirements-container.txt").is_file(), "CP7 container requirements missing")
    require((ROOT / ".dockerignore").is_file(), "CP7 .dockerignore missing")
    candidate_file, metadata = locate_candidate()
    registry_model = validate_registry()
    # Only deserialize the pinned locally generated joblib file, never arbitrary files.
    candidate_model = joblib.load(candidate_file)
    candidate_diff, registry_diff, count = validate_prediction_parity(
        candidate_model, registry_model, metadata
    )
    status = export_bundle(candidate_file, metadata, candidate_diff, registry_diff, count)

    print("\nPROJECT 12 - CP7 VERIFIED MODEL BUNDLE")
    print("=" * 47)
    print("Model:", REGISTERED_NAME, "version", REGISTERED_VERSION)
    print("Candidate status: candidate_not_promoted")
    print("Frozen test records:", count)
    print("CP3 candidate probability max difference:", f"{candidate_diff:.3e}")
    print("MLflow registered probability max difference:", f"{registry_diff:.3e}")
    print("Model SHA-256:", CANDIDATE_SHA)
    print("Output:", OUTPUT)
    print("Export status:", status)
    print("Bundle files:", ARTIFACT_NAME, "+", MANIFEST_NAME)
    print("RESULT: CP7 MODEL BUNDLE VERIFIED")
    print("No model retraining, registration, promotion, or Docker build occurred.")


if __name__ == "__main__":
    main()
