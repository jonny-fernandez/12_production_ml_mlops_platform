"""Project 12: local inference settings and CP8 API security controls.

The model is a local synthetic-data candidate, not production-approved.
AUTH_REQUIRED is opt-in for local development and MUST be enabled for Docker
in the next CP8 checkpoint. Authentication never relaxes the model lock.
"""

from __future__ import annotations

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    auth_required: bool = False  # CP8 local-dev default; Docker must set true.
    api_key: SecretStr | None = None
    api_key_file: str | None = None  # Prefer a read-only Docker secret.
    model_name: str = "p09-attrition-gb"
    model_version: str = "1"
    model_threshold: float = 0.125
    model_bundle_dir: str | None = None
    model_release_approved: bool = False  # Only after explicit independent review
    model_release_approval_reference: str = ""
    database_url: str = "sqlite:///./mlops.db"
    mlflow_tracking_uri: str = "sqlite:///mlflow_tracking.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
