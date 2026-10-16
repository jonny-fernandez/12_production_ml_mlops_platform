"""Local-only, bounded CP16 security, readiness and load/failure rehearsal.

Uses fake synthetic feature input, a stub prediction model, and a fake credential.
This is NOT a production load benchmark or proof of a live AWS SLO.
"""
from __future__ import annotations
import json
import logging
from io import StringIO
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'src'))

import numpy as np
from fastapi.testclient import TestClient
from pydantic import SecretStr
from mlops_platform.api.main import app
from mlops_platform.api.observability import logger
from mlops_platform.config import settings
from mlops_platform.serving import realtime
from mlops_platform.monitoring.metrics import percentile

# Completely synthetic example, no employee IDs or actual workforce records.
INPUT={
 'department':'Development','job_family':'Data','job_level':'L2','location':'Chicago-North',
 'employment_type':'Full-Time','age':35,'tenure_months':24,'monthly_salary_annualized':70000.0,
 'overtime_hours_90d':4.5,'absences_90d':2,'performance_score':4.1,'engagement_score':72.0,
 'manager_changes_12m':1,'months_since_promotion':13,'commute_minutes':25,
 'training_hours_12m':20.0,'remote_work_ratio':0.4,'salary_change_pct_12m':0.04,
 'internal_moves_24m':1,
}
FAKE_KEY='cp16-fixture-'+'X'*48  # Not a real credential.
class FakeModel:
    def predict_proba(self, frame):
        if list(frame.columns)!=list(realtime.FEATURE_NAMES):
            raise AssertionError('Feature order mismatch')
        return np.tile(np.array([[0.8,0.2]]), (len(frame),1))

def exercise(request_count:int=40)->dict:
    if not 1<=request_count<=200:
        raise ValueError('Offline test bounded to 1..200 requests')
    stream=StringIO()
    handler=logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
    try:
        with (patch.object(settings,'app_env','local'),
              patch.object(settings,'auth_required',True),
              patch.object(settings,'api_key_file',None),
              patch.object(settings,'api_key',SecretStr(FAKE_KEY)),
              patch.object(realtime,'_load_model',lambda:FakeModel()),
              TestClient(app, raise_server_exceptions=False) as client):
            auth={'X-API-Key':FAKE_KEY}
            unauthorized=client.post('/predict',json={'features':INPUT}).status_code==401
            incorrect=client.post('/predict',json={'features':INPUT},headers={'X-API-Key':'not-a-real-key'}).status_code==401
            live=client.get('/health').status_code==200
            ready=client.get('/ready').status_code==200
            invalid=client.post('/predict',json={'features':{**INPUT,'employee_id':'NOT_A_REAL_PERSON'}},headers=auth).status_code==422
            elapsed=[]
            successful=0
            for _ in range(request_count):
                start=time.perf_counter()
                r=client.post('/predict',json={'features':INPUT},headers=auth)
                elapsed.append((time.perf_counter()-start)*1000)
                successful+=int(r.status_code==200 and r.json().get('prediction')==1)
            # Inject a model outage and confirm the API fails closed, then recovers.
            with patch.object(realtime,'_load_model',side_effect=realtime.ModelUnavailableError('sensitive-private-path')):
                outage=client.get('/ready').status_code==503 and client.post('/predict',json={'features':INPUT},headers=auth).status_code==503
            recovery=client.get('/ready').status_code==200
            corrected=client.post('/predict',json={'features':INPUT},headers=auth).status_code==200
    finally:
        logger.removeHandler(handler)
    raw=stream.getvalue()
    privacy=all(marker not in raw for marker in (FAKE_KEY,'NOT_A_REAL_PERSON','sensitive-private-path','not-a-real-key'))
    # All operational logs must be JSON allowlisted request records.
    parsed=[json.loads(line) for line in raw.splitlines() if line.strip()]
    log_schema=all(set(row)=={'event','request_id','method','route','status_code','duration_ms'} for row in parsed)
    checks={'unauthorized_rejected':unauthorized,'wrong_key_rejected':incorrect,'liveness_ok':live,
            'model_readiness_ok':ready,'invalid_input_rejected':invalid,
            'all_bounded_requests_succeeded':successful==request_count,
            'simulated_model_outage_fails_closed':outage,
            'simulated_model_recovery':recovery and corrected,
            'no_sensitive_content_in_logs':privacy,'structured_metadata_only':log_schema}
    result={'format':'project12_cp16_offline_reliability_v1','mode':'IN_PROCESS_FAKE_MODEL',
           'requests_attempted':request_count,'successful_responses':successful,
           'p95_testclient_latency_ms':round(percentile(elapsed,95),3),
           'note':'Synthetic in-process measurements. No live SLO, production throughput or AWS load claims.',
           'checks':checks,'status':'OFFLINE_PASSED' if all(checks.values()) else 'FAILED',
           'live_aws_exercise_completed':False}
    return result

def main()->int:
    report=exercise()
    dest=ROOT/'outputs/cp16_reliability_audit.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    for name,val in report['checks'].items():print(f'{name}: {"PASS" if val else "FAIL"}')
    print('Synthetic in-process p95 latency (ms):',report['p95_testclient_latency_ms'])
    print('RESULT:', 'CP16 OFFLINE RELIABILITY AUDIT PASSED' if report['status']=='OFFLINE_PASSED' else 'CP16 OFFLINE AUDIT FAILED')
    return 0 if report['status']=='OFFLINE_PASSED' else 1

if __name__=='__main__':
    raise SystemExit(main())
