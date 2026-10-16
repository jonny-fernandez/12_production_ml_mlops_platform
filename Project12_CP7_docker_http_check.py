r"""Project 12 | CP7: verify the running local Docker API over real HTTP.

From the Project 12 repository root in PowerShell:
    .\.venv\Scripts\python.exe .\Project12_CP7_docker_http_check.py

Requires the sibling Project 9 source data, the already-running Docker API at
127.0.0.1:8000, and only Python standard-library packages.

Read-only HTTP GET/POST checks. No training, registry writes, container builds,
model promotion, external API services, or changes to any local files.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "09_ai_attrition_prediction"
MODEL_NAME = "p09-attrition-gb"
MODEL_VERSION = "1"
THRESHOLD = 0.125
TOLERANCE = 1e-8
BATCH_LIMIT = 1000

CATEGORICAL = {"department", "job_family", "job_level", "location", "employment_type"}
INTEGERS = {
    "age", "tenure_months", "absences_90d", "manager_changes_12m",
    "months_since_promotion", "commute_minutes", "internal_moves_24m",
}


def require(condition: bool, description: str) -> None:
    if not condition:
        raise AssertionError(description)


def load_frozen_records() -> tuple[list[dict], list[dict]]:
    metadata_file = SOURCE / "artifacts" / "model_metadata.json"
    raw_file = SOURCE / "data" / "raw" / "employee_attrition_snapshots_synthetic.csv"
    frozen_file = SOURCE / "outputs" / "final_test_predictions.csv"
    for path in (metadata_file, raw_file, frozen_file):
        require(path.is_file(), f"Missing Project 9 file: {path}")

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    features = list(metadata["feature_list"])
    require(len(features) == 19 and len(set(features)) == 19, "Expected 19 unique features")
    require(float(metadata["operating_threshold"]) == THRESHOLD, "Threshold changed")
    require(CATEGORICAL.isdisjoint(INTEGERS) and CATEGORICAL | INTEGERS <= set(features),
            "Expected model feature types are missing")

    with raw_file.open(encoding="utf-8-sig", newline="") as handle:
        data = list(csv.DictReader(handle))
    with frozen_file.open(encoding="utf-8-sig", newline="") as handle:
        frozen = list(csv.DictReader(handle))
    require(len(frozen) == 507, f"Expected 507 saved predictions, found {len(frozen)}")

    keyed_data: dict[tuple[str, str], dict] = {}
    for row in data:
        key = (row["employee_id"], row["snapshot_date"])
        require(key not in keyed_data, f"Duplicate raw-data key: {key}")
        keyed_data[key] = row

    payloads: list[dict] = []
    seen = set()
    for row in frozen:
        key = (row["employee_id"], row["snapshot_date"])
        require(key not in seen, f"Duplicate frozen test key: {key}")
        seen.add(key)
        require(key in keyed_data, f"Frozen row missing from source data: {key}")
        raw = keyed_data[key]
        require(raw["attrition_within_90_days"] == row["actual_target"],
                "Frozen test target differs from raw data")
        require(float(row["operating_threshold"]) == THRESHOLD,
                "Frozen prediction threshold changed")
        require(int(row["predicted_class"]) == int(float(row["predicted_probability"]) >= THRESHOLD),
                "Frozen saved prediction and threshold disagree")
        item: dict[str, object] = {}
        for feature in features:
            value = raw.get(feature)
            require(value not in (None, ""), f"Missing value in frozen feature: {feature}")
            if feature in CATEGORICAL:
                item[feature] = value
            elif feature in INTEGERS:
                item[feature] = int(value)
            else:
                item[feature] = float(value)
                require(math.isfinite(item[feature]), f"Nonfinite feature: {feature}")
        payloads.append({"features": item})
    return payloads, frozen


def request_json(base_url: str, method: str, path: str, payload: dict | None = None,
                 expected_status: int = 200) -> dict:
    body = None if payload is None else json.dumps(payload, allow_nan=False).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=120) as response:
            status = response.status
            content = response.read()
    except HTTPError as exc:
        status = exc.code
        content = exc.read()
    except URLError as exc:
        raise ConnectionError(
            f"Cannot reach local Docker API at {base_url}. Confirm 'docker compose ps' is healthy. "
            f"Original error: {exc}"
        ) from exc
    require(status == expected_status,
            f"{method} {path}: expected HTTP {expected_status}, got HTTP {status}: "
            f"{content[:700].decode('utf-8', errors='replace')}")
    try:
        result = json.loads(content)
    except (ValueError, UnicodeError) as exc:
        raise AssertionError(f"{method} {path}: response is not JSON") from exc
    require(isinstance(result, dict), f"{method} {path}: expected JSON object")
    return result


def compare_prediction(actual: dict, expected: dict, label: str) -> float:
    require(set(actual) == {"prediction", "probability", "model_name", "model_version"},
            f"{label}: unexpected response keys")
    require(actual["model_name"] == MODEL_NAME and actual["model_version"] == MODEL_VERSION,
            f"{label}: wrong model identity")
    p = float(actual["probability"])
    require(math.isfinite(p) and 0 <= p <= 1, f"{label}: invalid probability")
    difference = abs(p - float(expected["predicted_probability"]))
    require(difference <= TOLERANCE, f"{label}: prediction probability differs by {difference}")
    require(actual["prediction"] == int(expected["predicted_class"]),
            f"{label}: wrong predicted class")
    require(actual["prediction"] == int(p >= THRESHOLD),
            f"{label}: incorrect decision threshold")
    return difference


def compare_batch(response: dict, saved: list[dict], label: str) -> float:
    require(response.get("count") == len(saved), f"{label}: count mismatch")
    predictions = response.get("predictions")
    require(isinstance(predictions, list) and len(predictions) == len(saved),
            f"{label}: prediction list size mismatch")
    return max((compare_prediction(actual, expected, f"{label} row {index}")
                for index, (actual, expected) in enumerate(zip(predictions, saved))), default=0.0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000",
                        help="Local Docker API address (default: http://127.0.0.1:8000)")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    require(base_url.startswith("http://127.0.0.1:") or base_url.startswith("http://localhost:"),
            "CP7 must use a local-only HTTP endpoint")
    require(Path.cwd().resolve() == ROOT.resolve(), "Run from Project 12 repository root")
    payloads, frozen = load_frozen_records()

    print("\nPROJECT 12 - CP7 REAL DOCKER HTTP CHECK")
    print("=" * 50)
    print("Endpoint:", base_url)
    print("Registered model:", MODEL_NAME, "version", MODEL_VERSION)
    print("Frozen Project 9 predictions:", len(frozen))

    health = request_json(base_url, "GET", "/health")
    require(health == {"status": "ok"}, "Unexpected /health response")
    print("GET /health: PASS (HTTP 200)")

    info = request_json(base_url, "GET", "/model/info")
    require(info == {"model_name": MODEL_NAME, "model_version": MODEL_VERSION},
            "Wrong /model/info identity")
    print("GET /model/info: PASS (HTTP 200)")

    # Verify individual predictions for both classes through the real TCP HTTP path.
    for cls, label in ((0, "negative"), (1, "positive")):
        index = next((i for i, saved in enumerate(frozen)
                      if int(saved["predicted_class"]) == cls), None)
        require(index is not None, f"No {label} test record")
        result = request_json(base_url, "POST", "/predict", payloads[index])
        difference = compare_prediction(result, frozen[index], label)
        print(f"POST /predict ({label}): PASS (max difference {difference:.3g})")

    # Full historical parity and response order.
    result = request_json(base_url, "POST", "/predict/batch", {"items": payloads})
    difference = compare_batch(result, frozen, "507-row batch")
    classes = [x["prediction"] for x in result["predictions"]]
    require(classes.count(1) == 118 and classes.count(0) == 389,
            "Frozen positive/negative counts changed")
    print(f"POST /predict/batch (507 records): PASS (max difference {difference:.3g}; "
          "118 positive / 389 negative)")

    reversed_result = request_json(
        base_url, "POST", "/predict/batch", {"items": list(reversed(payloads))}
    )
    reversed_diff = compare_batch(reversed_result, list(reversed(frozen)), "Reverse order")
    print(f"POST /predict/batch (reversed 507): PASS (max difference {reversed_diff:.3g})")

    at_limit = (payloads * 2)[:BATCH_LIMIT]
    limit_result = request_json(base_url, "POST", "/predict/batch", {"items": at_limit})
    require(limit_result.get("count") == BATCH_LIMIT, "Batch limit of 1000 not accepted")
    print("POST /predict/batch (1000 records): PASS")

    request_json(base_url, "POST", "/predict/batch", {"items": at_limit + [payloads[0]]}, 422)
    print("POST /predict/batch (1001 records): PASS (HTTP 422)")
    request_json(base_url, "POST", "/predict/batch", {"items": []}, 422)
    print("POST /predict/batch (empty batch): PASS (HTTP 422)")

    invalid = dict(payloads[1]["features"])
    invalid["department"] = "Not a Department"
    request_json(base_url, "POST", "/predict/batch",
                 {"items": [payloads[0], {"features": invalid}]}, 422)
    print("POST /predict/batch (invalid second row): PASS (HTTP 422)")

    missing = dict(payloads[1]["features"])
    missing.pop("age")
    request_json(base_url, "POST", "/predict/batch",
                 {"items": [payloads[0], {"features": missing}]}, 422)
    print("POST /predict/batch (missing second-row feature): PASS (HTTP 422)")

    request_json(base_url, "POST", "/predict", {"features": invalid}, 422)
    print("POST /predict (unknown category): PASS (HTTP 422)")

    print("\nRESULT: CP7 DOCKER HTTP INFERENCE AND PARITY PASSED")
    print("All checks used localhost; no files, models, or registry versions were changed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nRESULT: CP7 DOCKER HTTP CHECK FAILED: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        raise SystemExit(1)
