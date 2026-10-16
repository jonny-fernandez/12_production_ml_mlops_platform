"""Regression checks for Project 12's read-only GitHub prepublication audit."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "GITHUB_PREP_AUDIT.py"
SPEC = importlib.util.spec_from_file_location("github_prep_audit", PATH)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


@pytest.mark.parametrize("filename", [
    ".env", "./.env", ".env.local", ".secrets/api_key.txt", ".venv/pyvenv.cfg",
    "artifacts/cp9_cloud_candidate/candidate_model_pipeline.joblib",
    "outputs/cp13_drift_report.json", "data/raw/synthetic.csv",
    "infrastructure/terraform/terraform.tfstate",
    "infrastructure/terraform/aws.auto.tfvars",
    "mlflow_tracking.db", "other/model.joblib",
])
def test_private_paths_never_count_as_publishable(filename):
    assert AUDIT.unsafe_path(filename)


@pytest.mark.parametrize("filename", [
    ".env.example", "README.md", "screenshots/final/01_full_pytest_suite.png",
    "infrastructure/terraform/.terraform.lock.hcl", "CP9_SAFE_DEFAULTS.tfvars.example",
    "artifacts/.gitkeep", "data/raw/.gitkeep", "outputs/.gitkeep",
])
def test_allowed_repository_files_not_blocked(filename):
    assert not AUDIT.unsafe_path(filename)


def test_png_signature_locked():
    assert AUDIT.PNG_HEADER == bytes.fromhex("89504e470d0a1a0a")
    assert len(AUDIT.REQUIRED_PNGS) == 8
