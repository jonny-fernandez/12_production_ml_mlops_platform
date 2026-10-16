"""CP12 deterministic service-level indicators from CP8's sanitized JSON logs.

Consumes only allowlisted operational metadata. Never stores requests, feature
values, authentication headers, identities, or raw user payloads.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
from typing import Iterable

ROUTES = frozenset(("/health", "/ready", "/model/info", "/predict", "/predict/batch"))


@dataclass(frozen=True)
class ServiceMetrics:
    request_count: int
    error_count: int
    p95_latency_ms: float

    @property
    def error_rate(self) -> float:
        return self.error_count / self.request_count if self.request_count else 0.0


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    if not 0 <= percentile_value <= 100:
        raise ValueError("Invalid percentile")
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile_value / 100
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def summarize_requests(events: Iterable[dict], minimum_requests: int = 25) -> dict:
    """Summarize CP8 JSON metadata, no raw events are retained in output."""
    by_route: dict[str, dict[str, list | int]] = {}
    total = errors = unauthorized = 0
    durations: list[float] = []
    for event in events:
        if not isinstance(event, dict) or event.get("event") != "http_request":
            continue
        route = event.get("route")
        code = event.get("status_code")
        duration = event.get("duration_ms")
        if (route not in ROUTES and route != "/unmatched") or type(code) is not int or not 100 <= code <= 599:
            continue
        if type(duration) not in (float, int) or not math.isfinite(duration) or duration < 0:
            continue
        total += 1
        error = code >= 500
        errors += int(error)
        unauthorized += int(code == 401)
        durations.append(float(duration))
        bucket = by_route.setdefault(route, {"count": 0, "errors_5xx": 0, "latencies": []})
        bucket["count"] += 1
        bucket["errors_5xx"] += int(error)
        bucket["latencies"].append(float(duration))
    aggregate = ServiceMetrics(total, errors, round(percentile(durations, 95), 3))
    return {
        "format": "project12_cp12_sli_v1",
        "status": "INSUFFICIENT_DATA" if total < minimum_requests else "MEASURED",
        "request_count": aggregate.request_count,
        "error_count_5xx": aggregate.error_count,
        "error_rate_5xx": round(aggregate.error_rate, 6),
        "unauthorized_401_count": unauthorized,
        "p95_latency_ms": aggregate.p95_latency_ms,
        "routes": {route: {
            "request_count": int(info["count"]),
            "error_count_5xx": int(info["errors_5xx"]),
            "p95_latency_ms": round(percentile(info["latencies"], 95), 3),
        } for route, info in sorted(by_route.items())},
        "notes": "Metadata only; no input features, secrets, IP addresses or request IDs retained.",
    }


def summarize_json_lines(lines: Iterable[str], minimum_requests: int = 25) -> dict:
    records = []
    for line in lines:
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue  # Ignore non-JSON Uvicorn/container startup log lines.
        if type(event) is dict:
            records.append(event)
    return summarize_requests(records, minimum_requests=minimum_requests)
