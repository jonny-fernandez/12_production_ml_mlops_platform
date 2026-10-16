"""Privacy-safe JSON request logs: metadata only, never features or secrets."""

from __future__ import annotations

import json
import logging
import secrets
import sys
import time

from fastapi import Request


logger = logging.getLogger("mlops_platform.request")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

_ROUTES = frozenset({"/health", "/ready", "/model/info", "/predict", "/predict/batch"})


async def request_audit_middleware(request: Request, call_next):
    """Emit only an allowlisted path, status, duration, and generated ID."""
    request_id = secrets.token_hex(8)
    started = time.monotonic()
    code = 500
    try:
        response = await call_next(request)
        code = response.status_code
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    finally:
        logger.info(json.dumps({
            "event": "http_request",
            "request_id": request_id,
            "method": request.method if request.method in {"GET", "POST"} else "OTHER",
            "route": request.url.path if request.url.path in _ROUTES else "/unmatched",
            "status_code": code,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }, separators=(",", ":")))
