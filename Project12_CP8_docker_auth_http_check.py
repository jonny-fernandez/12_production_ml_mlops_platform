"""Project 12 CP8 — local Docker authentication, readiness and model-parity check.

Run from Project 12 root (the CP8 Docker container must be running):
    .\\.venv\\Scripts\\python.exe .\\Project12_CP8_docker_auth_http_check.py

Only accesses http://127.0.0.1:8000 and reads local Project 9 synthetic
fixtures plus .secrets/api_key.txt. The key is never displayed or logged.
No files, model versions, registry entries or Docker resources are modified.
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "09_ai_attrition_prediction"
URL = "http://127.0.0.1:8000"
NAME, VERSION, THRESHOLD = "p09-attrition-gb", "1", 0.125
TOL = 1e-8
CATEGORICAL = {"department", "job_family", "job_level", "location", "employment_type"}
INTEGERS = {"age", "tenure_months", "absences_90d", "manager_changes_12m",
            "months_since_promotion", "commute_minutes", "internal_moves_24m"}


def check(value: bool, label: str) -> None:
    if not value:
        raise AssertionError(label)


def load_secret() -> str:
    secret_file = ROOT / ".secrets" / "api_key.txt"
    check(secret_file.is_file() and not secret_file.is_symlink(),
          "Expected a regular local .secrets/api_key.txt; do not paste the key")
    key = secret_file.read_text(encoding="utf-8").rstrip("\r\n")
    check(32 <= len(key) <= 256 and not any(c.isspace() for c in key),
          "API secret does not have the expected format")
    return key


def query(method: str, path: str, payload: dict | None = None,
          *, key: str | None = None, status: int = 200) -> dict:
    encoded = json.dumps(payload, allow_nan=False).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if encoded is not None:
        headers["Content-Type"] = "application/json"
    if key is not None:
        headers["X-API-Key"] = key
    request = Request(URL + path, data=encoded, headers=headers, method=method)
    try:
        with urlopen(request, timeout=120) as response:
            got, raw = response.status, response.read()
    except HTTPError as exc:
        got, raw = exc.code, exc.read()
    except (URLError, TimeoutError, ConnectionError) as exc:
        raise RuntimeError("Unable to connect to local Docker API; check docker compose ps and logs") from exc
    check(got == status, f"{method} {path}: expected HTTP {status}, got HTTP {got}")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise AssertionError(f"{method} {path}: non-JSON response") from exc
    check(isinstance(result, dict), f"{method} {path}: response was not an object")
    return result


def frozen_rows() -> tuple[list[dict], list[dict]]:
    meta_file = SOURCE / "artifacts" / "model_metadata.json"
    input_file = SOURCE / "data" / "raw" / "employee_attrition_snapshots_synthetic.csv"
    saved_file = SOURCE / "outputs" / "final_test_predictions.csv"
    for path in (meta_file, input_file, saved_file):
        check(path.is_file(), f"Missing Project 9 source file: {path}")
    metadata = json.loads(meta_file.read_text(encoding="utf-8"))
    features = list(metadata["feature_list"])
    check(len(features) == 19 and len(set(features)) == 19, "Feature schema mismatch")
    check(float(metadata["operating_threshold"]) == THRESHOLD, "Threshold mismatch")
    with input_file.open(newline="", encoding="utf-8-sig") as handle:
        source = list(csv.DictReader(handle))
    with saved_file.open(newline="", encoding="utf-8-sig") as handle:
        saved = list(csv.DictReader(handle))
    check(len(saved) == 507, "Expected 507 frozen test records")
    index = {}
    for row in source:
        k = (row["employee_id"], row["snapshot_date"])
        check(k not in index, "Duplicate source record")
        index[k] = row
    payloads = []
    seen = set()
    for row in saved:
        k = (row["employee_id"], row["snapshot_date"])
        check(k in index and k not in seen, "Frozen record missing or duplicated")
        seen.add(k)
        raw = index[k]
        check(raw["attrition_within_90_days"] == row["actual_target"],
              "Frozen outcome changed")
        check(float(row["operating_threshold"]) == THRESHOLD, "Frozen threshold changed")
        check(int(row["predicted_class"]) ==
              int(float(row["predicted_probability"]) >= THRESHOLD),
              "Frozen class and probability disagree")
        item = {}
        for feature in features:
            value = raw.get(feature)
            check(value not in (None, ""), "Missing frozen model feature")
            if feature in CATEGORICAL:
                item[feature] = value
            elif feature in INTEGERS:
                item[feature] = int(value)
            else:
                value = float(value)
                check(math.isfinite(value), "Nonfinite frozen feature")
                item[feature] = value
        payloads.append({"features": item})
    return payloads, saved


def parity(actual: dict, expected: dict) -> float:
    check(set(actual) == {"model_name", "model_version", "prediction", "probability"},
          "Inference response schema changed")
    check(actual["model_name"] == NAME and actual["model_version"] == VERSION,
          "Inference model identity changed")
    p = float(actual["probability"])
    check(math.isfinite(p) and 0.0 <= p <= 1.0, "Invalid model probability")
    delta = abs(p - float(expected["predicted_probability"]))
    check(delta <= TOL, f"Probability parity failed; difference={delta}")
    check(actual["prediction"] == int(expected["predicted_class"]) == int(p >= THRESHOLD),
          "Inference class/threshold mismatch")
    return delta


def batch_parity(actual: dict, expected: list[dict]) -> float:
    check(actual.get("count") == len(expected), "Batch count mismatch")
    preds = actual.get("predictions")
    check(isinstance(preds, list) and len(preds) == len(expected), "Batch shape mismatch")
    return max((parity(x, y) for x, y in zip(preds, expected)), default=0.0)


def wait_for_ready(seconds: int = 90) -> None:
    """Avoid restart-race failures while the container is still becoming healthy."""
    deadline = time.monotonic() + seconds
    while True:
        try:
            check(query("GET", "/ready") == {"status": "ready"},
                  "Unexpected readiness payload")
            return
        except (RuntimeError, AssertionError) as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "Local Docker /ready did not become ready within 90 seconds. "
                    "Check 'docker compose ps' and 'docker compose logs --tail 60 api'."
                ) from exc
            time.sleep(3)


def main() -> None:
    check(Path.cwd().resolve() == ROOT.resolve(), "Run from Project 12 project root")
    key = load_secret()
    inputs, saved = frozen_rows()
    print("\nPROJECT 12 — CP8 SECURED DOCKER HTTP CHECK")
    print("=" * 48)
    print("Endpoint: 127.0.0.1:8000 (local only)")
    print("Registered model:", NAME, "version", VERSION)
    print("Frozen Project 9 predictions:", len(saved))
    print("API secret: loaded privately (never displayed)")

    wait_for_ready()
    check(query("GET", "/health") == {"status": "ok"}, "Liveness failed")
    print("GET /health without key: PASS (HTTP 200)")
    check(query("GET", "/ready") == {"status": "ready"}, "Model readiness failed")
    print("GET /ready without key: PASS (HTTP 200, model ready)")

    query("GET", "/model/info", status=401)
    print("GET /model/info without key: PASS (HTTP 401)")
    query("GET", "/model/info", key="definitely-invalid-key", status=401)
    print("GET /model/info with wrong key: PASS (HTTP 401)")
    query("POST", "/predict", inputs[0], status=401)
    print("POST /predict without key: PASS (HTTP 401)")
    query("POST", "/predict/batch", {"items": [inputs[0]]}, status=401)
    print("POST /predict/batch without key: PASS (HTTP 401)")

    info = query("GET", "/model/info", key=key)
    check(info == {"model_name": NAME, "model_version": VERSION}, "Model version mismatch")
    print("GET /model/info with correct key: PASS (HTTP 200)")

    for cls, label in ((0, "negative"), (1, "positive")):
        pos = next(i for i, record in enumerate(saved) if int(record["predicted_class"]) == cls)
        diff = parity(query("POST", "/predict", inputs[pos], key=key), saved[pos])
        print(f"POST /predict ({label}) authenticated: PASS (max difference {diff:.3g})")

    result = query("POST", "/predict/batch", {"items": inputs}, key=key)
    diff = batch_parity(result, saved)
    counts = [item["prediction"] for item in result["predictions"]]
    check(counts.count(1) == 118 and counts.count(0) == 389,
          "Expected positive/negative counts changed")
    print(f"POST /predict/batch (507) authenticated: PASS (max difference {diff:.3g})")

    result = query("POST", "/predict/batch", {"items": list(reversed(inputs))}, key=key)
    diff = batch_parity(result, list(reversed(saved)))
    print(f"POST /predict/batch (reversed 507): PASS (max difference {diff:.3g})")

    at_limit = (inputs * 2)[:1000]
    check(query("POST", "/predict/batch", {"items": at_limit}, key=key)["count"] == 1000,
          "1000-record batch failed")
    print("POST /predict/batch (1000 records): PASS")
    query("POST", "/predict/batch", {"items": at_limit + [inputs[0]]}, key=key, status=422)
    print("POST /predict/batch (1001 records): PASS (HTTP 422)")
    query("POST", "/predict/batch", {"items": []}, key=key, status=422)
    print("POST /predict/batch (empty batch): PASS (HTTP 422)")
    malformed = dict(inputs[0]["features"])
    malformed["department"] = "Unknown Department"
    query("POST", "/predict", {"features": malformed}, key=key, status=422)
    print("POST /predict (unknown category): PASS (HTTP 422)")
    query("POST", "/predict/batch", {"items": [inputs[0], {"features": malformed}]},
          key=key, status=422)
    print("POST /predict/batch (invalid second row): PASS (HTTP 422)")

    print("\nRESULT: CP8 SECURE DOCKER AUTHENTICATION AND PREDICTION PARITY PASSED")
    print("Read-only local requests; no key printed and no models or files changed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nRESULT: CP8 SECURE DOCKER CHECK FAILED: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        raise SystemExit(1)
