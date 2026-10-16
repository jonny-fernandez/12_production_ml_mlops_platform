"""CP17 evidence inventory with strict screenshot/publication hold. No git write."""
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REQUIRED=(
 '01_full_pytest_suite.png',
 '02_terraform_validation.png',
 '03_mlflow_registered_model.png',
 '04_docker_container_healthy.png',
 '05_secured_prediction_parity.png',
 '06_cp13_drift_report.png',
 '07_cp16_reliability_audit.png',
 '08_cp15_ci_configuration.png',
)
OPTIONAL=(
 '09_actual_github_actions_ci.png', '10_live_https_endpoint.png', '11_live_cloudwatch_dashboard.png',
 '12_aws_release_rollback_exercise.png',
)

def inventory(root:Path=ROOT)->dict:
    docs=['docs/MODEL_CARD.md','docs/INCIDENT_RESPONSE.md','docs/SCREENSHOT_PLAN.md',
          'docs/CP15_17_HANDOFF.md','docs/CP11_AWS_DEPLOYMENT_AND_COST_RUNBOOK.md']
    doc_checks={name:(root/name).is_file() and (root/name).stat().st_size>100 for name in docs}
    folder=root/'screenshots/final'
    found={name:(folder/name).is_file() for name in REQUIRED}
    optional={name:(folder/name).is_file() for name in OPTIONAL}
    word=root/'outputs/Project12_Final_Screenshot_Handoff.docx'
    return {'format':'project12_cp17_evidence_inventory_v1',
            'documentation_checks':doc_checks,
            'required_screenshots':found,
            'optional_live_screenshots':optional,
            'word_handoff_exists':word.is_file(),
            'github_publication_authorized':False,
            'aws_deployment_verified':False,
            'status':'OFFLINE_DOCS_READY_PUBLICATION_BLOCKED' if all(doc_checks.values()) else 'MISSING_DOCUMENTATION',
            'note':'Never equate offline validation with live deployment, CI on GitHub, or final publication.'}

def main()->int:
    r=inventory()
    path=ROOT/'outputs/cp17_evidence_inventory.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    for p,ok in r['documentation_checks'].items(): print(f'{p}: {"PASS" if ok else "MISSING"}')
    print('Screenshots saved:',sum(r['required_screenshots'].values()),'/',len(REQUIRED))
    print('Word screenshot handoff:', 'PRESENT' if r['word_handoff_exists'] else 'PENDING')
    print('Publication:', 'BLOCKED (await screenshots, verification, user confirmation)')
    print('RESULT:', 'CP17 OFFLINE DOCUMENTATION AUDIT PASSED - PUBLICATION BLOCKED' if r['status'].startswith('OFFLINE_') else 'CP17 DOC AUDIT FAILED')
    return 0 if r['status'].startswith('OFFLINE_') else 1

if __name__=='__main__':
    raise SystemExit(main())
