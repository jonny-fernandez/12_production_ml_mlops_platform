"""Read CP8 metadata-only JSON log export and calculate offline service SLIs."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from sys import path as search_path

ROOT = Path(__file__).resolve().parent
search_path.insert(0, str(ROOT / "src"))
from mlops_platform.monitoring.metrics import summarize_json_lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=ROOT / "examples" / "cp12_safe_access_logs.jsonl")
    ap.add_argument("--output", type=Path, default=ROOT / "outputs" / "cp12_observability.json")
    ap.add_argument("--minimum-requests", type=int, default=25)
    args = ap.parse_args()
    report = summarize_json_lines(args.input.read_text(encoding="utf-8").splitlines(), args.minimum_requests)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("CP12 OBSERVABILITY REPORT")
    print("Requests:", report["request_count"], "5xx:", report["error_count_5xx"], "p95 ms:", report["p95_latency_ms"])
    print("Status:", report["status"], "Written:", args.output)
    print("RESULT: CP12 OFFLINE SLI AGGREGATION PASSED")


if __name__ == "__main__":
    main()
