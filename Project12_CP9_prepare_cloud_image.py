"""Prepare a review-only CP9 cloud image context. No AWS calls.

Default is inspection only. --assemble requires an independent approved record
from the user, explicit reference, and confirmation, and never generates an
approval or promotes a candidate. The generated directory is Git-ignored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from mlops_platform.serving.cloud_candidate import inspect_candidate  # noqa: E402
from mlops_platform.serving.cloud_release import verify_cloud_release  # noqa: E402


def copy_safe_tree(source: Path, destination: Path) -> None:
    for current, dirs, files in os.walk(source, followlinks=False):
        rel = Path(current).relative_to(source)
        for directory in list(dirs):
            if directory.startswith(".") or directory == "__pycache__" or (Path(current) / directory).is_symlink():
                dirs.remove(directory)
        (destination / rel).mkdir(parents=True, exist_ok=True)
        for name in files:
            src = Path(current) / name
            if src.is_symlink() or src.suffix in {".pyc", ".pyo"}:
                continue
            if src.suffix != ".py" and name != "py.typed":
                continue
            shutil.copyfile(src, destination / rel / name)


def prepare(root: Path, approval_file: Path | None, reference: str | None, assemble: bool) -> None:
    if Path.cwd().resolve() != root.resolve():
        raise RuntimeError("Run from the Project 12 repository root")
    candidate = root / "artifacts" / "cp9_cloud_candidate"
    verified = inspect_candidate(candidate)
    print("Verified pinned candidate:", verified.model_sha256)
    print("Approval status: pending_review; model is not yet approved for public serving")
    print("Terraform apply: NOT invoked")
    if not assemble:
        print("RESULT: CP9 CLOUD IMAGE DESIGN PREFLIGHT PASSED - RELEASE STILL BLOCKED")
        return
    if not approval_file or not reference:
        raise RuntimeError("--assemble requires --approval-file and --approval-reference")
    if not approval_file.is_file() or approval_file.is_symlink():
        raise RuntimeError("Approval file must be a regular existing JSON file")
    if not os.environ.get("PROJECT12_RELEASE_REVIEW_ACK") == "YES_REVIEWED":
        raise RuntimeError("Explicit PROJECT12_RELEASE_REVIEW_ACK=YES_REVIEWED is required")
    with tempfile.TemporaryDirectory(prefix=".cp9_review_", dir=root / "artifacts") as tmp:
        temp = Path(tmp)
        model_folder = temp / "model"
        (model_folder / "candidate").mkdir(parents=True)
        shutil.copyfile(verified.model_path, model_folder / "candidate" / verified.model_path.name)
        shutil.copyfile(verified.manifest_path, model_folder / "candidate" / verified.manifest_path.name)
        shutil.copyfile(approval_file, model_folder / "release_approval.json")
        verify_cloud_release(model_folder, reference)
        shutil.copyfile(root / "Dockerfile.cloud", temp / "Dockerfile")
        shutil.copyfile(root / "requirements-container.txt", temp / "requirements-container.txt")
        copy_safe_tree(root / "src" / "mlops_platform", temp / "src" / "mlops_platform")
        (temp / ".dockerignore").write_text("**/__pycache__/\n**/*.pyc\n.env\n.secrets/\n", encoding="utf-8")
        destination = root / "artifacts" / "cp9_cloud_image_context"
        if destination.exists():
            raise RuntimeError("Existing build context must be reviewed/removed manually; never overwrite")
        shutil.copytree(temp, destination)
    print("Review-ready, isolated cloud image build context:", destination)
    print("Model approval record copied after verification. No image built or pushed.")
    print("RESULT: CP9 APPROVED IMAGE CONTEXT ASSEMBLED (NOT DEPLOYED)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assemble", action="store_true", help="Only after independent release approval")
    parser.add_argument("--approval-file", type=Path, help="Independently reviewed approval JSON; never create here")
    parser.add_argument("--approval-reference", help="External review record ID, matched to JSON")
    args = parser.parse_args()
    prepare(ROOT, args.approval_file, args.approval_reference, args.assemble)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("CP9 IMAGE PREP FAILED:", type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(1)
