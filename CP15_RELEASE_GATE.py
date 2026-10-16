"""CP15 CI/CD release safety review: read-only, never approves or deploys."""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLAGS = ('enable_aws_resources','enable_public_https','enable_ecs_deployment',
         'cloud_runtime_verified','model_release_approved')
FORBIDDEN_WORKFLOW = (
    'terraform apply', 'aws ecs update-service', 'aws ecs create-service',
    'aws ecr get-login-password', 'aws configure', 'kubectl apply',
    'docker push', 'model_release_approved=true',
)

def assess(root: Path = ROOT) -> dict:
    checks = {}
    ci = root / '.github/workflows/ci.yml'
    dep = root / '.github/workflows/deploy.yml'
    checks['workflows_present'] = ci.is_file() and dep.is_file()
    ci_source = ci.read_text(encoding='utf-8') if ci.is_file() else ''
    deploy_source = dep.read_text(encoding='utf-8') if dep.is_file() else ''
    combined = (ci_source + '\n' + deploy_source).lower()
    checks['workflow_no_live_deployment_commands'] = all(s not in combined for s in FORBIDDEN_WORKFLOW)
    checks['workflow_no_write_permissions'] = 'contents: write' not in combined and 'id-token: write' not in combined
    checks['ci_runs_python_312'] = "python-version: '3.12'" in ci_source
    checks['ci_covers_test_and_audit'] = all(x in ci_source for x in (
        'CP15_RELEASE_GATE.py', 'pytest', 'CP16_RELIABILITY_AUDIT.py',
        'CP17_EVIDENCE_AUDIT.py', 'terraform', 'docker build'))
    tfdir = root / 'infrastructure/terraform'
    all_tf = '\n'.join(p.read_text(encoding='utf-8') for p in tfdir.glob('*.tf'))
    checks['terraform_defaults_disabled'] = all(
        len(matches := re.findall(r'variable\s+"'+re.escape(flag)+r'"\s*\{([^{}]*)\}', all_tf)) == 1
        and bool(re.search(r'\bdefault\s*=\s*false\b', matches[0])) for flag in FLAGS
    )
    template = root / 'CP9_RELEASE_APPROVAL_TEMPLATE.json'
    try:
        approval = json.loads(template.read_text(encoding='utf-8'))
        checks['model_approval_template_blocked'] = approval.get('approved') is False
    except (ValueError, OSError):
        checks['model_approval_template_blocked'] = False
    checks['no_approval_file_bundled'] = not (root / 'artifacts' / 'cp9_cloud_candidate' / 'release_approval.json').exists()
    checks['packaging_ignores_secrets'] = all(x in (root/'.dockerignore').read_text(encoding='utf-8')
            for x in ('.env', 'artifacts/', 'data/')) if (root/'.dockerignore').is_file() else False
    return {
        'format': 'project12_cp15_release_review_v1',
        'checks': checks, 'safety_checks_passed': all(checks.values()),
        'release_status': 'BLOCKED_PENDING_INDEPENDENT_APPROVAL',
        'aws_deployment_executed': False, 'registry_mutated': False,
        'note': 'Static safety review does not certify a live AWS release or signed approval.',
    }

def main() -> int:
    report = assess()
    for key, value in report['checks'].items():
        print(f'{key}: {"PASS" if value else "FAIL"}')
    dest = ROOT / 'outputs/cp15_release_gate.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n',encoding='utf-8')
    print('Release status:', report['release_status'])
    print('Result:', 'CP15 OFFLINE CI/CD GATES PASSED - RELEASE BLOCKED' if report['safety_checks_passed'] else 'CP15 GATE CHECK FAILED')
    return 0 if report['safety_checks_passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
