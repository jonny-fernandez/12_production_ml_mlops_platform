PROJECT 12 - CP9 STEP 11: CLOUD-CANDIDATE RUNTIME OFFLINE REHEARSAL

OBJECTIVE
Validate the staged model package using portable (Windows/Linux) paths,
original SHA-256, original feature order and all 507 frozen Project 9
predictions. Confirm the current APP_ENV=cloud service still fails closed.

This is NOT a deployable release and does NOT change existing FastAPI serving.

INSTALL (preserve paths, add new files only)
  src/mlops_platform/serving/cloud_candidate.py
  tests/test_cp9_cloud_runtime.py
  Project12_CP9_cloud_runtime_dry_run.py

REQUIRES
  - Existing successful CP9 Step 9 staging in artifacts/cp9_cloud_candidate/
  - Existing Project12_CP7_docker_http_check.py in repository root
  - Adjacent Project 9 repository with 507 frozen test records
  - Existing Project 12 .venv with scikit-learn, joblib, pandas, pytest

RUN FROM PROJECT 12 ROOT
  .\.venv\Scripts\python.exe .\Project12_CP9_cloud_runtime_dry_run.py

EXPECTED
  RESULT: CP9 CLOUD RUNTIME OFFLINE REHEARSAL PASSED - RELEASE STILL BLOCKED

Do NOT deploy to AWS, set any Terraform enable_* to true, or approve model.
After this passes, run the full test suite as a separate checkpoint.

SECURITY BOUNDARY
- The manifest/hash is checked before offline joblib deserialization.
- Joblib is executable pickle; only locally produced pinned bytes are accepted.
- No AWS/HTTP calls and no file modifications are required.
- Existing APP_ENV=cloud model serving intentionally stays disabled.
- Future cloud-serving enablement requires separately reviewed model approval,
  release manifest verification, image digest, and cloud runtime parity tests.
