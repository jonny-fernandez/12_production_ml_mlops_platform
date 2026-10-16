"""CP11 local-only release prerequisite inspection: NEVER calls AWS or Terraform apply."""
from __future__ import annotations
import json
import re
from pathlib import Path
from sys import exit

ROOT = Path(__file__).resolve().parent
TERRAFORM = ROOT / "infrastructure" / "terraform"
GATES = ("enable_aws_resources", "enable_public_https", "enable_ecs_deployment",
         "cloud_runtime_verified", "model_release_approved")


def gate_defaults_safe() -> dict[str, bool]:
    source = "\n".join(p.read_text(encoding="utf-8") for p in TERRAFORM.glob("*.tf"))
    safe = {}
    for name in GATES:
        blocks = list(re.finditer(r'variable\s+"' + re.escape(name) + r'"\s*\{([^{}]*)\}', source))
        safe[name] = len(blocks) == 1 and bool(re.search(r'\bdefault\s*=\s*false\b', blocks[0].group(1)))
    return safe


def run() -> bool:
    safe = gate_defaults_safe()
    print("PROJECT 12 CP11 — AWS DEPLOYMENT PRECHECK (READ-ONLY)")
    for key, ok in safe.items():
        print(f"Terraform {key} defaults false:", "PASS" if ok else "FAIL")
    for p in (TERRAFORM / "public_https_ecs_service.tf", ROOT / "Dockerfile.cloud", ROOT / "CP9_RELEASE_APPROVAL_TEMPLATE.json"):
        print("Present:", p.relative_to(ROOT), p.is_file())
        if not p.is_file():
            return False
    approval = json.loads((ROOT / "CP9_RELEASE_APPROVAL_TEMPLATE.json").read_text(encoding="utf-8"))
    no_approval = approval.get("approved") is False
    print("Model approval remains false:", "PASS" if no_approval else "FAIL")
    print("Missing for live deployment: AWS account/permissions; verified domain + issued ACM cert; Secrets Manager ARN;")
    print("independent model approval; reviewed image digest; controlled terraform plan; cost budget; rollback plan.")
    ok = all(safe.values()) and no_approval
    print("RESULT:", "CP11 DESIGN PREFLIGHT PASSED — LIVE DEPLOYMENT NOT AUTHORIZED" if ok else "CP11 PRECHECK FAILED")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if run() else 1)
