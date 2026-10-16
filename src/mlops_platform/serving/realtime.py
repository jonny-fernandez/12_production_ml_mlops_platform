"""Pinned Project 9 model inference for local registry and CP7 Docker bundle.

Both paths use the same previously validated Project 9 / Project 12 model.
The Docker path is enabled only by MODEL_BUNDLE_DIR; it validates the exported
manifest and pinned artifact hash BEFORE deserializing the trusted joblib file.
Neither path authorizes production serving of an unpromoted candidate.
"""

from __future__ import annotations

import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

import pandas as pd

from mlops_platform.config import settings
from mlops_platform.schemas import FEATURE_NAMES, PredictionRequest, PredictionResponse

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_NAME = "p09-attrition-gb"
EXPECTED_VERSION = "1"
EXPECTED_THRESHOLD = 0.125
EXPECTED_CANDIDATE_SHA256 = (
    "27585a4b8443be29a7cf41a5a2bfd3227ae4a66d8dd947afd88d38111f404d43"
)
EXPECTED_SOURCE_SHA256 = (
    "12f9c529ecaffe70f8c1ad401ab398e25b135d8a5ecab6edd71584d65a126755"
)
EXPECTED_RUN_ID = "0a2731b4c9c64abfb373166e22b1f97e"
BUNDLE_MODEL_FILENAME = "candidate_model_pipeline.joblib"
BUNDLE_MANIFEST_FILENAME = "model_bundle_manifest.json"
PARITY_TOLERANCE = 1e-8


class ModelUnavailableError(RuntimeError):
    """The pinned candidate cannot safely serve this request."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_pipeline(model):
    """Enforce the locked API interface, regardless of its loading route."""
    if tuple(getattr(model, "feature_names_in_", ())) != FEATURE_NAMES:
        raise ModelUnavailableError("Model feature ordering differs from CP2 lock")
    if tuple(int(item) for item in getattr(model, "classes_", ())) != (0, 1):
        raise ModelUnavailableError("Unexpected model class labels")
    if not callable(getattr(model, "predict_proba", None)):
        raise ModelUnavailableError("Model does not support probability inference")
    return model


def _load_verified_bundle(bundle_dir: Path):
    """Load only the pinned, SHA-256-verified model exported by CP7.

    Local trusted bundle; joblib/pickle must NEVER be used with external input.
    """
    if not bundle_dir.is_absolute() or not bundle_dir.is_dir():
        raise ModelUnavailableError("MODEL_BUNDLE_DIR must be an existing absolute directory")
    manifest_path = bundle_dir / BUNDLE_MANIFEST_FILENAME
    model_path = bundle_dir / BUNDLE_MODEL_FILENAME
    if any(path.is_symlink() or not path.is_file() for path in (manifest_path, model_path)):
        raise ModelUnavailableError("Verified model bundle files are missing or not regular files")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ModelUnavailableError("Verified model bundle manifest is unreadable") from exc
    if not isinstance(manifest, dict):
        raise ModelUnavailableError("Invalid model bundle manifest")

    expected_fields = {
        "format": "project12_verified_local_joblib_v1",
        "model_name": EXPECTED_NAME,
        "model_version": EXPECTED_VERSION,
        "source_mlflow_run_id": EXPECTED_RUN_ID,
        "candidate_status": "candidate_not_promoted",
        "synthetic_data_only": True,
        "operating_threshold": EXPECTED_THRESHOLD,
        "candidate_model_sha256": EXPECTED_CANDIDATE_SHA256,
        "source_model_sha256": EXPECTED_SOURCE_SHA256,
        "model_filename": BUNDLE_MODEL_FILENAME,
        "feature_list": list(FEATURE_NAMES),
        "test_records": 507,
    }
    for field, expected in expected_fields.items():
        if type(manifest.get(field)) is not type(expected) or manifest[field] != expected:
            raise ModelUnavailableError(f"Verified model bundle metadata mismatch: {field}")
    for field in ("candidate_frozen_max_difference", "registry_frozen_max_difference"):
        value = manifest.get(field)
        if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= PARITY_TOLERANCE:
            raise ModelUnavailableError(f"Verified model bundle parity evidence invalid: {field}")

    # Verify BEFORE calling joblib.load: Python pickle formats can execute code.
    if _sha256(model_path) != EXPECTED_CANDIDATE_SHA256:
        raise ModelUnavailableError("Pinned model bundle SHA-256 mismatch")
    try:
        import joblib

        model = joblib.load(model_path)
    except Exception as exc:
        raise ModelUnavailableError("Pinned model bundle failed to deserialize") from exc
    return _validate_pipeline(model)


def _load_local_registry_model():
    """Unchanged CP5/CP6 Windows development route through local MLflow."""
    if Path.cwd().resolve() != ROOT.resolve():
        raise ModelUnavailableError("Start Project 12 from its repository root")
    if not (ROOT / "mlflow_tracking.db").is_file():
        raise ModelUnavailableError("Local MLflow tracking database not found")

    import mlflow
    import mlflow.sklearn
    from mlflow.tracking import MlflowClient

    uri = settings.mlflow_tracking_uri
    if uri != "sqlite:///mlflow_tracking.db":
        raise ModelUnavailableError("CP5 requires the local CP4 tracking database")
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    client = MlflowClient(tracking_uri=uri, registry_uri=uri)
    version = client.get_model_version(EXPECTED_NAME, EXPECTED_VERSION)

    if version.status != "READY":
        raise ModelUnavailableError("Registered model version is not READY")
    if version.tags.get("candidate_status") != "candidate_not_promoted":
        raise ModelUnavailableError("Unexpected approval status for CP5 candidate")
    if version.tags.get("candidate_sha256") != EXPECTED_CANDIDATE_SHA256:
        raise ModelUnavailableError("Model source provenance SHA-256 mismatch")
    if float(version.tags.get("operating_threshold", "nan")) != EXPECTED_THRESHOLD:
        raise ModelUnavailableError("Registry threshold differs from locked 0.125")
    if version.tags.get("synthetic_data_only") != "true":
        raise ModelUnavailableError("Only synthetic evaluation model allowed")

    model = mlflow.sklearn.load_model(f"models:/{EXPECTED_NAME}/{EXPECTED_VERSION}")
    return _validate_pipeline(model)


@lru_cache(maxsize=1)
def _load_model():
    """Load a single verified pipeline for both real-time and batch requests."""
    env = settings.app_env.lower()
    if (
        settings.model_name != EXPECTED_NAME
        or settings.model_version != EXPECTED_VERSION
        or settings.model_threshold != EXPECTED_THRESHOLD
    ):
        raise ModelUnavailableError("Model identity or threshold differs from CP2 lock")
    if env == "cloud":
        # An unapproved candidate is NEVER cloud-servable, even with valid bytes.
        if not settings.model_release_approved or not settings.auth_required:
            raise ModelUnavailableError("Unpromoted candidate cannot serve outside local mode")
        if not settings.model_bundle_dir or not settings.model_release_approval_reference:
            raise ModelUnavailableError("Cloud model release configuration incomplete")
        from mlops_platform.serving.cloud_release import CloudReleaseError, load_approved_cloud_model
        try:
            return _validate_pipeline(load_approved_cloud_model(
                Path(settings.model_bundle_dir), settings.model_release_approval_reference
            ))
        except (CloudReleaseError, ValueError, OSError) as exc:
            raise ModelUnavailableError("Approved cloud model verification failed") from exc
    if env != "local":
        raise ModelUnavailableError("Unrecognized model-serving environment")
    if settings.model_bundle_dir:
        return _load_verified_bundle(Path(settings.model_bundle_dir))
    return _load_local_registry_model()


def predict_one(payload: PredictionRequest) -> PredictionResponse:
    """Predict from the pinned pipeline at the validation-selected threshold."""
    model = _load_model()
    dataframe = pd.DataFrame([payload.features.model_dump()], columns=list(FEATURE_NAMES))
    try:
        probabilities = model.predict_proba(dataframe)
        score = float(probabilities[0, 1])
    except Exception as exc:
        raise ModelUnavailableError("Model inference failed") from exc
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ModelUnavailableError("Pipeline returned an invalid probability")
    return PredictionResponse(
        prediction=int(score >= EXPECTED_THRESHOLD),
        probability=score,
        model_name=EXPECTED_NAME,
        model_version=EXPECTED_VERSION,
    )
