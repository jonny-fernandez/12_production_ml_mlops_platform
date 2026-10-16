"""CP9 Step 11 - portable candidate OFFLINE runtime rehearsal, not cloud serving.

Run from Project 12 repository root with the existing .venv Python:
    .\\.venv\\Scripts\\python.exe .\\Project12_CP9_cloud_runtime_dry_run.py

It validates staged model bytes before a trusted joblib load and reproduces
Project 9's 507 frozen predictions. It then verifies APP_ENV=cloud still cannot
serve this unapproved candidate. It does NOT approve the model, build an image,
change Terraform state, contact AWS, or start the API.
"""

from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from mlops_platform.config import settings  # noqa: E402
from mlops_platform.serving import realtime  # noqa: E402
from mlops_platform.serving.cloud_candidate import inspect_candidate  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if Path.cwd().resolve() != ROOT.resolve():
        raise RuntimeError("Run this script from the Project 12 repository root")
    candidate = ROOT / "artifacts" / "cp9_cloud_candidate"
    before = {p.name: sha256(p) for p in candidate.iterdir()} if candidate.is_dir() else {}
    checked = inspect_candidate(candidate)

    # Import the proven CP7 fixture loader to reuse the original 507 source/frozen keys.
    from Project12_CP7_docker_http_check import load_frozen_records
    import joblib
    import pandas as pd

    requests, frozen = load_frozen_records()
    if len(requests) != 507 or len(frozen) != 507:
        raise AssertionError("Expected all 507 historical prediction records")
    # This is trusted OFFLINE analysis only, after exact checksum verification.
    model = joblib.load(checked.model_path)
    if tuple(getattr(model, "feature_names_in_", ())) != checked.feature_names:
        raise AssertionError("Model feature order differs from CP2 lock")
    if tuple(int(c) for c in model.classes_) != (0, 1):
        raise AssertionError("Unexpected model classes")
    frame = pd.DataFrame([req["features"] for req in requests], columns=list(checked.feature_names))
    scores = model.predict_proba(frame)[:, 1]
    if len(scores) != 507:
        raise AssertionError("Wrong prediction count")
    diffs = []
    counts = {0: 0, 1: 0}
    for score, saved in zip(scores, frozen):
        score = float(score)
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise AssertionError("Invalid prediction probability")
        diff = abs(score - float(saved["predicted_probability"]))
        if diff > 1e-8:
            raise AssertionError(f"Frozen probability parity failure: {diff}")
        cls = int(score >= checked.threshold)
        if cls != int(saved["predicted_class"]):
            raise AssertionError("Prediction class parity failure")
        counts[cls] += 1
        diffs.append(diff)
    if counts != {0: 389, 1: 118}:
        raise AssertionError("Frozen class counts differ")

    # This is NOT cloud-serving authorization. Assert the existing API guard
    # continues to reject APP_ENV=cloud, even with a valid model bundle.
    old_env, old_bundle = settings.app_env, settings.model_bundle_dir
    try:
        settings.app_env = "cloud"
        settings.model_bundle_dir = str(candidate)
        realtime._load_model.cache_clear()
        try:
            realtime._load_model()
        except realtime.ModelUnavailableError:
            blocked = True
        else:
            blocked = False
    finally:
        settings.app_env = old_env
        settings.model_bundle_dir = old_bundle
        realtime._load_model.cache_clear()
    if not blocked:
        raise AssertionError("Unapproved APP_ENV=cloud serving was incorrectly allowed")

    after = {p.name: sha256(p) for p in candidate.iterdir()}
    if before != after:
        raise AssertionError("Candidate files were modified during inspection")

    print("PROJECT 12 - CP9 PORTABLE CLOUD RUNTIME OFFLINE REHEARSAL")
    print("=" * 58)
    print("Portable manifest and pinned model SHA-256: PASS")
    print("Recorded approval status: pending_review")
    print("Frozen test predictions:", len(frozen))
    print("Maximum probability difference:", f"{max(diffs):.3g}")
    print("Predicted classes: 118 positive / 389 negative")
    print("APP_ENV=cloud still rejects unapproved candidate: PASS")
    print("No artifacts modified, no cloud serving or approval: PASS")
    print("RESULT: CP9 CLOUD RUNTIME OFFLINE REHEARSAL PASSED - RELEASE STILL BLOCKED")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("RESULT: CP9 CLOUD RUNTIME OFFLINE REHEARSAL FAILED:",
              type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(1)
