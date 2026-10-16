"""CP15-17 safety regression tests. No remote APIs, cloud deployment or registry writes."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

def load_script(filename):
    spec = importlib.util.spec_from_file_location(filename, ROOT/f'{filename}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ci_gate_has_all_controls():
    result=load_script('CP15_RELEASE_GATE').assess()
    assert result['safety_checks_passed'] and all(result['checks'].values())


def test_ci_gate_release_remains_blocked():
    result=load_script('CP15_RELEASE_GATE').assess()
    assert result['release_status']=='BLOCKED_PENDING_INDEPENDENT_APPROVAL'
    assert result['aws_deployment_executed'] is False
    assert result['registry_mutated'] is False


def test_ci_gate_detects_unauthorized_workflow_write(tmp_path):
    from shutil import copytree
    testroot=tmp_path/'project'
    (testroot/'.github/workflows').mkdir(parents=True)
    (testroot/'infrastructure/terraform').mkdir(parents=True)
    for item in ('.github/workflows/ci.yml','.github/workflows/deploy.yml',
                 'infrastructure/terraform/main.tf','CP9_RELEASE_APPROVAL_TEMPLATE.json','.dockerignore'):
        src=ROOT/item
        dst=testroot/item;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
    t=testroot/'.github/workflows/ci.yml'
    t.write_text(t.read_text(encoding='utf-8')+'\n# contents: write\n')
    assert load_script('CP15_RELEASE_GATE').assess(testroot)['checks']['workflow_no_write_permissions'] is False


def test_ci_workflows_not_deploying():
    scripts='\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'.github/workflows').glob('*.yml'))
    for line in ('terraform apply','docker push','kubectl apply','aws ecs update-service'):
        assert line not in scripts


def test_python_ci_is_312():
    assert "python-version: '3.12'" in (ROOT/'.github/workflows/ci.yml').read_text()


def test_ci_terraform_static_checks_enabled():
    source=(ROOT/'.github/workflows/ci.yml').read_text()
    assert 'terraform -chdir=infrastructure/terraform validate' in source
    assert 'terraform -chdir=infrastructure/terraform fmt -check' in source


def test_ci_docker_build_only_no_push():
    source=(ROOT/'.github/workflows/ci.yml').read_text()
    assert 'docker build' in source and 'docker push' not in source


def test_cp16_test_bounded():
    with pytest.raises(ValueError):load_script('CP16_RELIABILITY_AUDIT').exercise(0)
    with pytest.raises(ValueError):load_script('CP16_RELIABILITY_AUDIT').exercise(201)


def test_cp16_rehearsal_passes_with_fake_model():
    result=load_script('CP16_RELIABILITY_AUDIT').exercise(3)
    assert result['status']=='OFFLINE_PASSED'
    assert result['requests_attempted']==3
    assert result['successful_responses']==3
    assert result['live_aws_exercise_completed'] is False


def test_cp16_simulated_outage_and_recovery():
    result=load_script('CP16_RELIABILITY_AUDIT').exercise(1)
    assert result['checks']['simulated_model_outage_fails_closed']
    assert result['checks']['simulated_model_recovery']


def test_cp16_no_sensitive_log_content():
    result=load_script('CP16_RELIABILITY_AUDIT').exercise(1)
    assert result['checks']['no_sensitive_content_in_logs']
    assert result['checks']['structured_metadata_only']


def test_cp16_not_production_benchmark():
    result=load_script('CP16_RELIABILITY_AUDIT').exercise(1)
    assert result['mode']=='IN_PROCESS_FAKE_MODEL'
    assert 'No live SLO' in result['note']


def test_cp17_screenshots_do_not_fake_presence(tmp_path):
    result=load_script('CP17_EVIDENCE_AUDIT').inventory(tmp_path)
    assert not all(result['required_screenshots'].values())
    assert result['github_publication_authorized'] is False


def test_cp17_required_eight_screen_filenames():
    mod=load_script('CP17_EVIDENCE_AUDIT')
    assert len(mod.REQUIRED)==8
    assert len(set(mod.REQUIRED))==8
    assert all(name.endswith('.png') for name in mod.REQUIRED)


def test_cp17_docs_are_available():
    result=load_script('CP17_EVIDENCE_AUDIT').inventory()
    assert all(result['documentation_checks'].values())
    assert result['status']=='OFFLINE_DOCS_READY_PUBLICATION_BLOCKED'


def test_cp17_word_generator_rejects_missing_images(tmp_path):
    mod=load_script('CP17_BUILD_SCREENSHOT_DOC')
    with pytest.raises(FileNotFoundError):mod.build(tmp_path,tmp_path/'out.docx')


def test_cp17_word_descriptions_match_required_images():
    mod=load_script('CP17_BUILD_SCREENSHOT_DOC')
    assert all(name in mod.DESCRIPTIONS for name in mod.REQUIRED)


def test_publication_cannot_be_marked_complete_from_offline_tests():
    result=load_script('CP17_EVIDENCE_AUDIT').inventory()
    assert result['github_publication_authorized'] is False
    assert result['aws_deployment_verified'] is False


def test_cp16_repository_audit_safe_defaults():
    result=load_script('CP16_REPOSITORY_AUDIT').run_audit()
    assert result['status'].startswith('PASS_')
    assert result['checks']['model_release_template_unapproved'] is True
    assert result['checks']['container_versions_pinned'] is True


def test_cp16_repository_audit_cannot_claim_git_check_without_git(tmp_path):
    repo=tmp_path/'no-git'
    repo.mkdir()
    result=load_script('CP16_REPOSITORY_AUDIT').run_audit(repo)
    assert result['git_initialized'] is False
    assert result['checks']['tracked_secrets_absent'] is None
    assert result['status']=='FAIL'  # Missing ignore policies cause fail, not false confidence.


def test_cp17_optional_github_run_not_required_before_publication():
    mod=load_script('CP17_EVIDENCE_AUDIT')
    assert '08_cp15_ci_configuration.png' in mod.REQUIRED
    assert '09_actual_github_actions_ci.png' in mod.OPTIONAL
