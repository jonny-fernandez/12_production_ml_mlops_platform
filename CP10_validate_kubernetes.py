r"""CP10 offline Kubernetes manifest validation. No cluster, AWS, or secrets needed.

Run: .\.venv\Scripts\python.exe .\CP10_validate_kubernetes.py
Requires PyYAML (provided by the existing MLflow environment, or see CP10_RUNBOOK.md).
"""
from __future__ import annotations
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print('ERROR: PyYAML is missing from this Python environment. See CP10_RUNBOOK.md.')
    sys.exit(2)

ROOT = Path(__file__).resolve().parent
K8S = ROOT / 'infrastructure' / 'kubernetes'
IMAGE_PLACEHOLDER = 'registry.invalid/project12/approved-api@sha256:' + '0'*64


def load_manifests(directory: Path = K8S):
    files = ('namespace.yaml', 'serviceaccount.yaml', 'deployment.yaml',
             'service.yaml', 'networkpolicy.yaml', 'kustomization.yaml')
    documents = {}
    for filename in files:
        path = directory / filename
        if not path.is_file():
            raise AssertionError(f'Missing Kubernetes file: {path}')
        item = yaml.safe_load(path.read_text(encoding='utf-8'))
        if not isinstance(item, dict):
            raise AssertionError(f'Invalid Kubernetes YAML: {filename}')
        documents[filename] = item
    return documents


def validate_manifests(docs):
    dep = docs['deployment.yaml']
    svc = docs['service.yaml']
    sa = docs['serviceaccount.yaml']
    ns = docs['namespace.yaml']
    np = docs['networkpolicy.yaml']
    kust = docs['kustomization.yaml']

    assert ns['kind'] == 'Namespace' and ns['metadata']['name'] == 'project12-mlops'
    assert sa['kind'] == 'ServiceAccount' and sa['automountServiceAccountToken'] is False
    assert dep['apiVersion'] == 'apps/v1' and dep['kind'] == 'Deployment'
    assert dep['metadata']['namespace'] == 'project12-mlops'
    assert dep['spec']['replicas'] == 0, 'Fail closed: replicas must be zero'
    templ = dep['spec']['template']
    spec = templ['spec']
    assert dep['spec']['selector']['matchLabels'] == templ['metadata']['labels']
    assert spec['serviceAccountName'] == 'portfolio-mlops-api'
    assert spec['automountServiceAccountToken'] is False
    sec = spec['securityContext']
    assert sec['runAsNonRoot'] is True and sec['runAsUser'] == 10001
    assert sec['runAsGroup'] == 10001 and sec['fsGroup'] == 10001
    assert sec['seccompProfile']['type'] == 'RuntimeDefault'
    assert len(spec['containers']) == 1
    cont = spec['containers'][0]
    assert cont['image'] == IMAGE_PLACEHOLDER, 'Only placeholder immutable digest allowed during CP10'
    assert cont['ports'][0]['containerPort'] == 8000
    env = {e['name']: e.get('value') for e in cont['env']}
    for key, expected in {
        'APP_ENV': 'cloud', 'AUTH_REQUIRED': 'true',
        'API_KEY_FILE': '/run/secrets/api_key',
        'MODEL_BUNDLE_DIR': '/app/model',
        'MODEL_RELEASE_APPROVED': 'false', 'MODEL_NAME': 'p09-attrition-gb',
        'MODEL_VERSION': '1', 'MODEL_THRESHOLD': '0.125',
    }.items():
        assert env.get(key) == expected, f'Invalid fail-closed environment: {key}'
    assert 'API_KEY' not in env and 'MODEL_RELEASE_APPROVAL_REFERENCE' not in env
    security = cont['securityContext']
    assert security['readOnlyRootFilesystem'] is True
    assert security['allowPrivilegeEscalation'] is False
    assert security['capabilities']['drop'] == ['ALL']
    assert cont['livenessProbe']['httpGet']['path'] == '/health'
    assert cont['startupProbe']['httpGet']['path'] == '/health'
    assert cont['readinessProbe']['httpGet']['path'] == '/ready'
    assert cont['resources']['requests']['memory'] == '512Mi'
    assert cont['resources']['limits']['memory'] == '2Gi'
    mounts = {v['name']: v for v in cont['volumeMounts']}
    assert mounts['api-credential']['readOnly'] is True
    assert mounts['api-credential']['mountPath'] == '/run/secrets'
    assert mounts['tmp']['mountPath'] == '/tmp'
    volumes = {v['name']: v for v in spec['volumes']}
    assert volumes['api-credential']['secret']['secretName'] == 'project12-api-key'
    assert volumes['api-credential']['secret']['optional'] is False
    assert volumes['api-credential']['secret']['defaultMode'] == 288
    assert volumes['api-credential']['secret']['items'] == [{'key': 'api_key', 'path': 'api_key'}]
    assert volumes['tmp']['emptyDir']['medium'] == 'Memory'
    assert svc['kind'] == 'Service' and svc['metadata']['namespace'] == 'project12-mlops'
    assert svc['spec']['type'] == 'ClusterIP', 'Never expose through a public Service in CP10'
    assert svc['spec']['selector'] == templ['metadata']['labels']
    assert svc['spec']['ports'][0]['targetPort'] == 'http'
    assert np['kind'] == 'NetworkPolicy'
    assert np['metadata']['namespace'] == 'project12-mlops'
    assert np['spec']['podSelector']['matchLabels'] == templ['metadata']['labels']
    assert np['spec']['policyTypes'] == ['Ingress']
    assert np['spec']['ingress'][0]['from'][0]['podSelector']['matchLabels'] == {'role': 'authorized-api-client'}
    assert np['spec']['ingress'][0]['ports'][0]['port'] == 8000
    assert kust['kind'] == 'Kustomization'
    assert set(kust['resources']) == set(docs) - {'kustomization.yaml'}
    return True


def main():
    docs = load_manifests()
    validate_manifests(docs)
    print('PROJECT 12 - CP10 KUBERNETES OFFLINE VALIDATION')
    print('===============================================')
    print('Kubernetes manifests: 5 resource files + Kustomize')
    print('Deployment replicas: 0 (disabled)')
    print('Container image: placeholder immutable digest')
    print('Cloud model release: blocked; no approval reference')
    print('Network: internal ClusterIP plus restricted ingress NetworkPolicy')
    print('Security: non-root, no privilege escalation, read-only root')
    print('Health: /health liveness and /ready readiness')
    print('Secrets: Kubernetes Secret reference only (no secret contents)')
    print('RESULT: CP10 OFFLINE KUBERNETES VALIDATION PASSED - DEPLOYMENT DISABLED')


if __name__ == '__main__':
    main()
