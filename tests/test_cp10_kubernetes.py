"""Permanent CP10 Kubernetes manifest tests: offline, no cluster or AWS."""
from __future__ import annotations
import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from CP10_validate_kubernetes import load_manifests, validate_manifests


@pytest.fixture
def docs():
    return load_manifests()


def test_full_manifest_contract(docs):
    assert validate_manifests(docs)


def test_kubernetes_namespace(docs):
    assert docs['namespace.yaml']['metadata']['name'] == 'project12-mlops'


def test_deployment_disabled_by_default(docs):
    assert docs['deployment.yaml']['spec']['replicas'] == 0


def test_image_is_placeholder_digest(docs):
    assert docs['deployment.yaml']['spec']['template']['spec']['containers'][0]['image'].startswith('registry.invalid/')


def test_not_public_service(docs):
    assert docs['service.yaml']['spec']['type'] == 'ClusterIP'


def test_readiness_checks_model(docs):
    assert docs['deployment.yaml']['spec']['template']['spec']['containers'][0]['readinessProbe']['httpGet']['path'] == '/ready'


def test_container_non_root(docs):
    assert docs['deployment.yaml']['spec']['template']['spec']['securityContext']['runAsUser'] == 10001


def test_container_root_readonly(docs):
    assert docs['deployment.yaml']['spec']['template']['spec']['containers'][0]['securityContext']['readOnlyRootFilesystem']


def test_service_account_token_disabled(docs):
    assert docs['deployment.yaml']['spec']['template']['spec']['automountServiceAccountToken'] is False


def test_secret_file_reference_not_literal_key(docs):
    c = docs['deployment.yaml']['spec']['template']['spec']['containers'][0]
    assert any(x['name'] == 'API_KEY_FILE' for x in c['env'])
    assert not any(x['name'] == 'API_KEY' for x in c['env'])


def test_network_policy_restricts_ingress(docs):
    assert docs['networkpolicy.yaml']['spec']['ingress'][0]['ports'][0]['port'] == 8000


@pytest.mark.parametrize('field,value', [
    ('replicas', 1),
    ('replicas', 2),
])
def test_validator_rejects_enabled_replicas(docs, field, value):
    broken = copy.deepcopy(docs)
    broken['deployment.yaml']['spec'][field] = value
    with pytest.raises(AssertionError):
        validate_manifests(broken)


def test_validator_rejects_public_service(docs):
    broken = copy.deepcopy(docs)
    broken['service.yaml']['spec']['type'] = 'LoadBalancer'
    with pytest.raises(AssertionError):
        validate_manifests(broken)


def test_validator_rejects_cloud_release_flag(docs):
    broken = copy.deepcopy(docs)
    container = broken['deployment.yaml']['spec']['template']['spec']['containers'][0]
    next(v for v in container['env'] if v['name'] == 'MODEL_RELEASE_APPROVED')['value'] = 'true'
    with pytest.raises(AssertionError):
        validate_manifests(broken)


def test_validator_rejects_unpinned_image(docs):
    broken = copy.deepcopy(docs)
    broken['deployment.yaml']['spec']['template']['spec']['containers'][0]['image'] = 'python:latest'
    with pytest.raises(AssertionError):
        validate_manifests(broken)


def test_validator_rejects_secret_literal(docs):
    broken = copy.deepcopy(docs)
    broken['deployment.yaml']['spec']['template']['spec']['containers'][0]['env'].append({'name':'API_KEY','value':'not-a-secret'})
    with pytest.raises(AssertionError):
        validate_manifests(broken)


def test_validator_rejects_unprotected_root(docs):
    broken = copy.deepcopy(docs)
    broken['deployment.yaml']['spec']['template']['spec']['containers'][0]['securityContext']['readOnlyRootFilesystem'] = False
    with pytest.raises(AssertionError):
        validate_manifests(broken)
