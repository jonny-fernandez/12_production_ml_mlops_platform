"""Read-only CP16 repository secret and reproducibility audit.

No files changed, no data uploaded. When Git is unavailable/uninitialized,
reports an explicit missing Git-stage verification instead of claiming success.
"""
from __future__ import annotations
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FORBIDDEN_TRACKED = re.compile(r'(^|/)(\.env($|\.)|\.secrets/|\.terraform/|[^/]+\.tfstate(?:\.|$)|[^/]+\.tfvars(?:\.|$)|mlflow_tracking\.db$|.+\.(?:pkl|pickle|joblib)$)',re.I)
LEAK_PATTERNS = (
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'sk-[A-Za-z0-9]{24,}'),
)
TEXT_EXT = frozenset({'.py','.md','.yml','.yaml','.tf','.ps1','.toml','.txt','.json','.example','.gitignore','.dockerignore'})
# Public placeholder template, intentionally tracked by Git; still scan its contents.
SAFE_TRACKED_TEMPLATES = frozenset({'.env.example'})

# CP9 deliberately publishes a documentation-only tfvars example.  Only this
# exact repository-root file may be tracked, and only with these safe values.
# No actual .tfvars, .auto.tfvars, or populated secret fields are exempted.
SAFE_CP9_EXAMPLE = 'CP9_SAFE_DEFAULTS.tfvars.example'
SAFE_CP9_VALUES = {
    'aws_region': '"us-east-1"',
    'environment': '"dev"',
    'enable_aws_resources': 'false',
    'enable_public_https': 'false',
    'enable_ecs_deployment': 'false',
    'cloud_runtime_verified': 'false',
    'model_release_approved': 'false',
    'manage_api_dns': 'false',
    'api_domain_name': '""',
    'acm_certificate_arn': '""',
    'api_key_secret_arn': '""',
    'release_approval_reference': '""',
    'approved_image_digest': '""',
    'route53_hosted_zone_id': '""',
    'ecs_desired_count': '1',
}

def cp9_example_is_safe(path: Path) -> bool:
    """Fail closed if the tracked Terraform example is populated or edited."""
    try:
        if not path.is_file() or path.stat().st_size > 16_384:
            return False
        assignments = {}
        for line in path.read_text(encoding='utf-8').splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            match = re.fullmatch(r'([a-z][a-z0-9_]*)\s*=\s*("[^"\n]*"|false|true|[0-9]+)', stripped)
            if not match:
                return False
            name, value = match.groups()
            if name in assignments:
                return False
            assignments[name] = value
        return assignments == SAFE_CP9_VALUES
    except (UnicodeError, OSError):
        return False


def run_audit(root:Path=ROOT)->dict:
    root=root.resolve()
    checks={
        'secret_ignores_present': all(x in (root/'.gitignore').read_text(encoding='utf-8') for x in ('.env','/.secrets/','*.tfstate','artifacts/*')) if (root/'.gitignore').is_file() else False,
        'container_does_not_copy_models': 'artifacts/' in (root/'.dockerignore').read_text(encoding='utf-8') if (root/'.dockerignore').is_file() else False,
        'model_release_template_unapproved': False,
        'ci_py312': (root/'.github/workflows/ci.yml').is_file() and "python-version: '3.12'" in (root/'.github/workflows/ci.yml').read_text(encoding='utf-8'),
        'container_versions_pinned': False,
    }
    approval=root/'CP9_RELEASE_APPROVAL_TEMPLATE.json'
    if approval.is_file():
        checks['model_release_template_unapproved']=json.loads(approval.read_text(encoding='utf-8')).get('approved') is False
    req=root/'requirements-container.txt'
    if req.is_file():
        lines=[x.strip() for x in req.read_text(encoding='utf-8').splitlines() if x.strip() and not x.strip().startswith('#')]
        checks['container_versions_pinned']=bool(lines) and all(re.fullmatch(r'[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+',x) for x in lines)
    try:
        cp=subprocess.run(['git','ls-files','-z'],cwd=root,capture_output=True,check=False)
        git_initialized=cp.returncode==0
    except FileNotFoundError:
        cp=None
        git_initialized=False
    tracked=[]
    unsafe=[]
    potential_leaks=[]
    if git_initialized:
        tracked=[p for p in cp.stdout.decode('utf-8','replace').split('\0') if p]
        unsafe=[]
        for p in tracked:
            normalized=p.replace('\\','/')
            if normalized == SAFE_CP9_EXAMPLE:
                if not cp9_example_is_safe(root / p):
                    unsafe.append(p)
                continue
            if normalized.lower() not in SAFE_TRACKED_TEMPLATES and FORBIDDEN_TRACKED.search(normalized):
                unsafe.append(p)
        for p in tracked:
            file=root/p
            if file.is_file() and file.stat().st_size<2_000_000 and (file.suffix.lower() in TEXT_EXT or file.name in {'.gitignore','.dockerignore'}):
                try: text=file.read_text(encoding='utf-8')
                except UnicodeError: continue
                if any(pattern.search(text) for pattern in LEAK_PATTERNS):
                    potential_leaks.append(p) # Only paths, NEVER the matched secret.
    checks['tracked_secrets_absent']=not unsafe if git_initialized else None
    checks['tracked_key_patterns_absent']=not potential_leaks if git_initialized else None
    status='FAIL' if any(v is False for v in checks.values()) else 'PASS_LOCAL_PENDING_GIT_REVIEW' if not git_initialized else 'PASS_TRACKED_FILES'
    return {'format':'project12_cp16_repository_audit_v1','status':status,
            'checks':checks,'git_initialized':git_initialized,
            'suspicious_paths_only':sorted(set(unsafe+potential_leaks)),
            'tracked_file_count':len(tracked),
            'caveat':'This scanner is not comprehensive; review code and history manually before GitHub publication.'}

def main()->int:
    r=run_audit()
    out=ROOT/'outputs/cp16_repository_audit.json';out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('Repository audit:',r['status'])
    for name,val in r['checks'].items():print(name, 'PASS' if val is True else 'NOT CHECKED' if val is None else 'FAIL')
    if r['suspicious_paths_only']:print('Files requiring private review:',r['suspicious_paths_only'])
    print('Git publication remains blocked until user screenshot confirmation.')
    return 1 if r['status']=='FAIL' else 0

if __name__=='__main__':
    raise SystemExit(main())
