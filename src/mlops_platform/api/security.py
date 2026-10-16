"""API-key authentication for local CP8 validation.

Never include keys, secret paths, headers or user input in logs/error bodies.
Enable with AUTH_REQUIRED=true and use API_KEY_FILE for Docker secrets.
"""

from __future__ import annotations

import hmac
from pathlib import Path

from fastapi import Header, HTTPException, status

from mlops_platform.config import settings


_MIN_KEY_LENGTH = 32
_INVALID_KEYS = {"replace_me", "changeme", "example", "placeholder", "test"}


def _valid_key() -> str | None:
    """Read the configured key; return None if absent/weak/invalid.

    Deliberately no caching: external secret rotation can be observed without
    persisting its value in application-level global state.
    """
    if settings.api_key_file:
        try:
            key_file = Path(settings.api_key_file)
            if not key_file.is_file() or key_file.is_symlink():
                return None
            key = key_file.read_text(encoding="utf-8").rstrip("\r\n")
        except (OSError, UnicodeError, ValueError):
            return None
    else:
        key = settings.api_key.get_secret_value() if settings.api_key else ""
    if (
        not isinstance(key, str)
        or len(key) < _MIN_KEY_LENGTH
        or len(key) > 256
        or any(char.isspace() for char in key)
        or key.lower() in _INVALID_KEYS
    ):
        return None
    return key


def authentication_ready() -> bool:
    """Check effective authentication configuration, not client credentials."""
    if not settings.auth_required and settings.app_env.lower() == "local":
        return True
    if not settings.auth_required:
        return False  # Fail closed for any non-local environment.
    return _valid_key() is not None


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Protect prediction and model metadata endpoints when auth is enabled."""
    if not settings.auth_required and settings.app_env.lower() == "local":
        return
    if not authentication_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API security configuration unavailable",
        )
    expected = _valid_key()
    if (
        expected is None
        or x_api_key is None
        or len(x_api_key) > 256
        or not hmac.compare_digest(x_api_key, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "ApiKey"},
        )
