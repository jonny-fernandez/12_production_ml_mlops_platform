"""Project 12 final PREPUBLICATION audit. Read-only; never stages, commits, or pushes.

Requires only Python standard library. Designed to audit the real LOCAL repo.
Printed diagnostics contain paths and counts, never the matched secret contents.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
REQUIRED_PNGS = (
    "01_full_pytest_suite.png", "02_terraform_validation.png",
    "03_mlflow_registered_model.png", "04_docker_container_healthy.png",
    "05_secured_prediction_parity.png", "06_cp13_drift_report.png",
    "07_cp16_reliability_audit.png", "08_cp15_ci_configuration.png",
)
REQUIRED_FILES = (
    "README.md", ".gitignore", ".dockerignore", ".env.example",
    "docs/ARCHITECTURE.md", "docs/ARCHITECTURE_DECISIONS.md",
    "docs/DEPLOYMENT_RUNBOOK.md", "docs/EVALUATION_PLAN.md",
    "docs/MODEL_CARD.md", "docs/INCIDENT_RESPONSE.md",
    "docs/SCREENSHOT_PLAN.md", "docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md",
    ".github/workflows/ci.yml", ".github/workflows/deploy.yml",
    "requirements-container.txt", "Dockerfile", "Dockerfile.cloud",
    "infrastructure/terraform/main.tf",
    "infrastructure/kubernetes/deployment.yaml",
    "CP9_RELEASE_APPROVAL_TEMPLATE.json",
)
# A deliberately conservative deny list. Do not publish even if someone bypassed .gitignore.
PRIVATE_PATH = re.compile(
    r"(^|/)(?:\.env(?:\..+)?|\.secrets|\.venv|venv|\.terraform|__pycache__|"
    r"mlruns|mlartifacts|outputs|logs|artifacts|data/raw|data/processed)(?:/|$)",
    re.IGNORECASE,
)
PRIVATE_SUFFIX = re.compile(
    r"(?:\.db(?:-shm|-wal)?|\.sqlite3?|\.joblib|\.pkl|\.pickle|\.tfstate(?:\..*)?|"
    r"\.tfplan(?:\..*)?|\.tfvars(?:\.json)?|\.auto\.tfvars(?:\.json)?|"
    r"\.pem|\.p12|\.pfx|\.key)$", re.IGNORECASE,
)
TEXT_SUFFIXES = {".py", ".md", ".tf", ".toml", ".ps1", ".yml", ".yaml",
                 ".txt", ".json", ".example", ".gitignore", ".dockerignore", ".sh"}
# High-confidence matches only. Additional manual review is still required.
KEY_SIGNATURES = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ASIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{32,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{24,}"),
)
MAX_PUBLIC_BYTES = 15 * 1024 * 1024


def cmd(*args: str) -> subprocess.CompletedProcess[bytes] | None:
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def git_pathset(*arguments: str) -> list[str] | None:
    process = cmd("git", "ls-files", "-z", *arguments)
    if process is None or process.returncode != 0:
        return None
    return [x for x in process.stdout.decode("utf-8", "replace").split("\0") if x]


def unsafe_path(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in {"artifacts/.gitkeep", "data/raw/.gitkeep", "data/processed/.gitkeep", "logs/.gitkeep", "outputs/.gitkeep"}:
        return False
    if normalized == ".env.example" or normalized.endswith("/.env.example"):
        return False
    if normalized.endswith(".tfvars.example") or normalized.endswith(".terraform.lock.hcl"):
        return False
    return bool(PRIVATE_PATH.search(normalized) or PRIVATE_SUFFIX.search(normalized))


def normalize_git_root_text(raw: str, *, windows: bool | None = None) -> str:
    """Translate Git Bash/MSYS /c/Users paths to Windows C:/Users paths.

    `git rev-parse --show-toplevel` can return `/c/Users/...` on Windows,
    which pathlib would otherwise resolve under an incorrect C:/c/Users path.
    """
    value = raw.strip()
    if windows is None:
        windows = os.name == "nt"
    if windows:
        match = re.match(r"^/([A-Za-z])(?=/|$)", value)
        if match:
            value = match.group(1).upper() + ":" + value[2:]
    return value


def same_git_root(git_root: Path, project_root: Path) -> bool:
    """Require the exact same existing directory, not a parent Git repo."""
    try:
        return git_root.samefile(project_root)
    except (OSError, ValueError):
        return False


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []
    print("PROJECT 12 - FINAL GITHUB PREPARATION AUDIT (READ ONLY)")
    print("=" * 59)

    missing = [p for p in REQUIRED_FILES if not (ROOT / p).is_file()]
    if missing:
        failures.append("Required documentation/configuration missing: " + ", ".join(missing))
    else:
        print(f"PASS: {len(REQUIRED_FILES)} required documentation/configuration files present")

    files = [ROOT / "screenshots/final" / f for f in REQUIRED_PNGS]
    invalid = []
    for path in files:
        try:
            with path.open("rb") as stream:
                ok = stream.read(8) == PNG_HEADER and path.stat().st_size > 1500
        except OSError:
            ok = False
        if not ok:
            invalid.append(path.name)
    if invalid:
        failures.append("Missing/invalid final screenshot PNGs: " + ", ".join(invalid))
    else:
        print("PASS: All 8 approved PNG filenames present with PNG signatures")

    word = ROOT / "outputs/Project12_Final_Screenshot_Handoff.docx"
    print("INFO: Local Word handoff:", "present (ignored output)" if word.exists() else "not found under outputs/")
    if not word.exists():
        warnings.append("Word handoff not in outputs/ (user already reviewed the uploaded copy)")

    if (ROOT / ".gitignore").is_file():
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        must_ignore = (".env", ".secrets/", "*.tfstate", "artifacts/*", "outputs/*", "*.joblib", "*.tfvars")
        if not all(p in gitignore for p in must_ignore):
            failures.append(".gitignore missing one or more required private-path patterns")
        else:
            print("PASS: Private files, binaries, Terraform state and generated output ignore patterns present")

    if (ROOT / "README.md").is_file():
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        if not all(s in readme for s in ("not deployed", "not approved", "507", "synthetic", "github actions")):
            failures.append("README missing one or more evidence/limitation disclaimers")
        else:
            print("PASS: README distinguishes verified local behavior from cloud/approval limitations")

    template = ROOT / "CP9_RELEASE_APPROVAL_TEMPLATE.json"
    if template.is_file():
        try:
            approval = json.loads(template.read_text(encoding="utf-8"))
            if approval.get("approved") is not False:
                failures.append("Cloud approval template does not remain approved=false")
            else:
                print("PASS: Model approval template remains unapproved")
        except (ValueError, OSError):
            failures.append("Cloud approval template unreadable")

    # True git-root check: do not mistake a parent portfolio repository for Project 12.
    repo = cmd("git", "rev-parse", "--show-toplevel")
    initialized = bool(repo and repo.returncode == 0)
    if initialized:
        try:
            raw_root = repo.stdout.decode("utf-8", "replace")
            git_root = Path(normalize_git_root_text(raw_root)).resolve()
        except (OSError, ValueError):
            git_root = Path("/")
        if not same_git_root(git_root, ROOT):
            failures.append("Git root is not Project 12: " + str(git_root))
        else:
            print("PASS: Git repository root matches Project 12")
        tracked = git_pathset("--cached")
        untracked = git_pathset("--others", "--exclude-standard")
        if tracked is None or untracked is None:
            failures.append("Unable to enumerate staged and untracked files")
            candidates: set[str] = set()
        else:
            candidates = set(tracked + untracked)
            print(f"INFO: Git candidates: {len(tracked)} tracked, {len(untracked)} untracked (after ignores)")
            insecure = sorted(path for path in candidates if unsafe_path(path))
            if insecure:
                failures.append("Sensitive/generated Git candidates: " + ", ".join(insecure[:20]))

        for relative in sorted(candidates):
            path = ROOT / relative
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_PUBLIC_BYTES:
                failures.append("Large file requires manual review: " + relative)
            if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".env.example", ".gitignore", ".dockerignore"}:
                continue
            if size > 2_000_000:
                warnings.append("Skipped scanning large text file: " + relative)
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                failures.append("Unreadable Git candidate: " + relative)
                continue
            if any(sig.search(content) for sig in KEY_SIGNATURES):
                failures.append("Potential credential pattern (path only): " + relative)

        # Verify ignore behavior, regardless of whether the paths currently exist.
        checks = {
            ".env": True,
            ".env.local": True,
            ".secrets/api_key.txt": True,
            "mlflow_tracking.db": True,
            "artifacts/cp7_container_model/candidate_model_pipeline.joblib": True,
            "outputs/report.json": True,
            "infrastructure/terraform/terraform.tfstate": True,
            "infrastructure/terraform/private.tfvars": True,
            ".env.example": False,
            "screenshots/final/01_full_pytest_suite.png": False,
            "infrastructure/terraform/.terraform.lock.hcl": False,
        }
        for relative, expected in checks.items():
            result = cmd("git", "check-ignore", "--no-index", "-q", relative)
            ignored = bool(result and result.returncode == 0)
            if ignored != expected:
                failures.append("Unexpected gitignore result: " + relative)
        if not any("gitignore" in message.lower() for message in failures):
            print("PASS: Git excludes private artifacts and retains approved screenshots/provider lock")
    else:
        warnings.append("Git not initialized here: tracked-file / stage audit requires git init and another run")
        print("PENDING: Git tracked/untracked candidate inspection (no local Git repository yet)")

    # Avoid confusing the approved user screenshot set with verified Git publication.
    print("INFO: No files were staged, committed, pushed, deployed, or approved")
    for warning in warnings:
        print("REVIEW:", warning)
    for failure in failures:
        print("FAIL:", failure)
    if failures:
        print("RESULT: GITHUB PREPARATION AUDIT FAILED - DO NOT STAGE OR PUBLISH")
        return 1
    if not initialized:
        print("RESULT: LOCAL PREPARATION PASSED - GIT INITIALIZATION/TRACKED-FILE AUDIT PENDING")
    else:
        print("RESULT: GITHUB PREPARATION AUDIT PASSED - USER REVIEW REQUIRED BEFORE STAGING/PUSH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
