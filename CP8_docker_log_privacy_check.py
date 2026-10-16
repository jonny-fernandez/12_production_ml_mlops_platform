"""CP8 Docker read-only audit of request-log privacy and baseline containment.

From the Project 12 repository root:
    .\\.venv\\Scripts\\python.exe .\\CP8_docker_log_privacy_check.py

Only sends two synthetic local requests, reads Docker metadata/logs, and checks
secret handling. Never prints the secret, log content, or synthetic canary.
"""
from __future__ import annotations

import json
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
HOST = "http://127.0.0.1:8000"
EXPECTED_FIELDS = {
    "event", "request_id", "method", "route", "status_code", "duration_ms"
}


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError(reason)


def docker(*args: str) -> str:
    result = subprocess.run(
        ["docker", *args], cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=35,
    )
    require(result.returncode == 0, "Docker command failed; check Docker Desktop and Compose")
    return result.stdout


def http(path: str, *, key: str | None, expected: int) -> tuple[int, str | None]:
    headers = {"Accept": "application/json"}
    if key is not None:
        headers["X-API-Key"] = key
    request = Request(HOST + path, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=12) as response:
            code = response.status
            request_id = response.headers.get("X-Request-ID")
    except HTTPError as exc:
        code = exc.code
        request_id = exc.headers.get("X-Request-ID")
        exc.close()
    except (URLError, TimeoutError, ConnectionError) as exc:
        raise RuntimeError("Local API was unreachable; check docker compose ps") from exc
    require(code == expected, f"Unexpected HTTP code (expected {expected}, got {code})")
    require(request_id is not None and re.fullmatch(r"[0-9a-f]{16}", request_id) is not None,
            "Missing or malformed X-Request-ID header")
    return code, request_id


def main() -> None:
    require(Path.cwd().resolve() == ROOT.resolve(), "Run from Project 12 root")
    secret_path = ROOT / ".secrets" / "api_key.txt"
    require(secret_path.is_file() and not secret_path.is_symlink(), "Missing local Docker API secret")
    api_key = secret_path.read_text(encoding="utf-8").rstrip("\r\n")
    require(32 <= len(api_key) <= 256, "Invalid local Docker API secret")
    cid = docker("compose", "ps", "-q", "api").strip()
    require(bool(cid), "Docker API container not found")
    raw = json.loads(docker("inspect", cid))
    require(isinstance(raw, list) and len(raw) == 1, "Unexpected Docker inspect result")
    info = raw[0]
    cfg = info["Config"]
    host_cfg = info["HostConfig"]
    require("--no-access-log" in cfg.get("Cmd", []),
            "Container still runs with Uvicorn access logs enabled; rebuild first")
    require(cfg.get("User") == "10001:10001", "Container is not configured as non-root")
    require(host_cfg.get("ReadonlyRootfs") is True, "Root filesystem is writable")
    require(host_cfg.get("Privileged") is False, "Container is privileged")
    require("ALL" in (host_cfg.get("CapDrop") or []), "Capabilities not dropped")
    require(any("no-new-privileges" in opt for opt in (host_cfg.get("SecurityOpt") or [])),
            "No-new-privileges is missing")
    require(any(m.get("Destination") == "/app/model" and m.get("RW") is False
                for m in info.get("Mounts", [])), "Model bundle mount is not read-only")
    ports = info.get("NetworkSettings", {}).get("Ports", {}).get("8000/tcp", [])
    require(bool(ports) and all(p.get("HostIp") in ("127.0.0.1", "::1") for p in ports),
            "API is not restricted to localhost")
    environment = cfg.get("Env") or []
    require(all(not e.startswith("API_KEY=") for e in environment),
            "API key is present in container environment")
    require("API_KEY_FILE=/run/secrets/api_key" in environment,
            "Expected file-based secret configuration missing")
    require(info.get("State", {}).get("Health", {}).get("Status") == "healthy",
            "Container has not reached healthy status")

    # A synthetic marker in the URL and an intentionally incorrect header value
    # detect unsafe Uvicorn access logs and accidental header logging.
    canary = "cp8-private-" + secrets.token_hex(12)
    _, first_id = http("/health?employee_identifier=" + quote(canary), key=None, expected=200)
    _, second_id = http("/model/info?email=" + quote(canary), key=canary, expected=401)
    _, third_id = http("/model/info", key=api_key, expected=200)
    time.sleep(1.5)
    logs = docker("compose", "logs", "--no-log-prefix", "--tail", "300", "api")
    require(canary not in logs, "Privacy failure: synthetic request marker appeared in logs")
    require(api_key not in logs, "Privacy failure: API key appeared in logs")

    structured = []
    for line in logs.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and entry.get("event") == "http_request":
            structured.append(entry)
    require(bool(structured), "No structured request-audit log entries found")
    by_id = {entry.get("request_id"): entry for entry in structured}
    for rid, route, status in [
        (first_id, "/health", 200),
        (second_id, "/model/info", 401),
        (third_id, "/model/info", 200),
    ]:
        require(rid in by_id, "Missing request audit record for test request")
        entry = by_id[rid]
        require(set(entry) == EXPECTED_FIELDS, "Structured log contains non-allowlisted fields")
        require(entry["route"] == route and entry["status_code"] == status,
                "Structured audit route/status does not match actual response")
        require(isinstance(entry["duration_ms"], (int, float)) and
                entry["duration_ms"] >= 0, "Invalid request duration metric")
    print("PROJECT 12 - CP8 LOCAL DOCKER PRIVACY AUDIT")
    print("=" * 45)
    print("Uvicorn access logging disabled: PASS")
    print("Non-root, read-only root, reduced privileges: PASS")
    print("Read-only model and localhost binding: PASS")
    print("File-based secret, absent from container environment: PASS")
    print("JSON request logs have allowlisted fields only: PASS")
    print("Unauthenticated 401 and authenticated 200 logged: PASS")
    print("Request identifiers correlate headers with logs: PASS")
    print("Secret and synthetic sensitive markers excluded from logs: PASS")
    print("RESULT: CP8 DOCKER LOG PRIVACY AUDIT PASSED")
    print("No secret values or raw logs displayed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("RESULT: CP8 DOCKER LOG PRIVACY AUDIT FAILED:", type(exc).__name__ + ":", str(exc),
              file=sys.stderr)
        raise SystemExit(1)
