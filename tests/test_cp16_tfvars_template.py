"""Regression tests for CP16 tracked Terraform template handling.

Only the exact unpopulated CP9 example is allowed.  Real .tfvars and
unsafe variants must still fail the repository security audit.
"""
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def audit_module():
    spec = importlib.util.spec_from_file_location("cp16_audit_template_guard", ROOT / "CP16_REPOSITORY_AUDIT.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def project(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".gitignore").write_text(".env\n/.secrets/\n*.tfstate\nartifacts/*\n", encoding="utf-8")
    (repo / ".dockerignore").write_text("artifacts/\n", encoding="utf-8")
    (repo / "CP9_RELEASE_APPROVAL_TEMPLATE.json").write_text('{"approved": false}', encoding="utf-8")
    (repo / "requirements-container.txt").write_text("fastapi==0.120.0\n", encoding="utf-8")
    ci = repo / ".github" / "workflows" / "ci.yml"
    ci.parent.mkdir(parents=True)
    ci.write_text("python-version: '3.12'\n", encoding="utf-8")
    module = audit_module()
    safe = repo / module.SAFE_CP9_EXAMPLE
    safe.write_text("# Not a deployment configuration\n" + "\n".join(
        f"{key} = {value}" for key, value in module.SAFE_CP9_VALUES.items()
    ) + "\n", encoding="utf-8")
    (repo / ".env.example").write_text("# API_KEY=<private>\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    return repo, safe


def test_safe_cp9_tfvars_example_is_allowed(project):
    repo, _ = project
    result = audit_module().run_audit(repo)
    assert result["status"] == "PASS_TRACKED_FILES"
    assert result["checks"]["tracked_secrets_absent"] is True


def test_enabling_deployment_in_example_is_rejected(project):
    repo, safe = project
    safe.write_text(safe.read_text(encoding="utf-8").replace(
        "enable_aws_resources = false", "enable_aws_resources = true"
    ), encoding="utf-8")
    result = audit_module().run_audit(repo)
    assert result["status"] == "FAIL"
    assert safe.name in result["suspicious_paths_only"]


def test_filled_secret_field_in_example_is_rejected(project):
    repo, safe = project
    safe.write_text(safe.read_text(encoding="utf-8").replace(
        'api_key_secret_arn = ""',
        'api_key_secret_arn = "arn:aws:secretsmanager:us-east-1:123456789012:secret:not-safe"',
    ), encoding="utf-8")
    result = audit_module().run_audit(repo)
    assert result["status"] == "FAIL"
    assert safe.name in result["suspicious_paths_only"]


def test_real_tfvars_file_is_still_rejected(project):
    repo, _ = project
    actual = repo / "production.tfvars"
    actual.write_text('aws_region = "us-east-1"\n', encoding="utf-8")
    subprocess.run(["git", "add", "-f", actual.name], cwd=repo, check=True)
    result = audit_module().run_audit(repo)
    assert result["status"] == "FAIL"
    assert actual.name in result["suspicious_paths_only"]


def test_real_env_file_is_still_rejected(project):
    repo, _ = project
    actual = repo / ".env"
    actual.write_text("API_KEY=this_is_a_fake_test_value\n", encoding="utf-8")
    subprocess.run(["git", "add", "-f", actual.name], cwd=repo, check=True)
    result = audit_module().run_audit(repo)
    assert result["status"] == "FAIL"
    assert actual.name in result["suspicious_paths_only"]
