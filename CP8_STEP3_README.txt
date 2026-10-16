PROJECT 12 — CP8 STEP 3: SECURE LOCAL DOCKER SECRET / READINESS CONFIG

CONTENTS (complete replacement files)
- docker-compose.yml         REPLACE existing
- .gitignore                 REPLACE existing starter-compatible version
- .dockerignore              REPLACE existing CP7 version
- CP8_create_local_secret.py NEW: creates secret only on YOUR computer

BEFORE EXTRACTING
- Extract into EXISTING 12_production_ml_mlops_platform project root.
- Preserve filenames, including leading dots. Avoid duplicating directories.
- Do not replace .env, model artifacts, Python inference modules, or MLflow database.
- These ignore files are based on the submitted project; if you've added custom
  ignore rules since CP7, merge them before replacing.

THIS STEP ONLY (IN PROJECT ROOT)
  .\.venv\Scripts\python.exe .\CP8_create_local_secret.py
  docker compose config --quiet
  docker compose config --services

EXPECTED
  RESULT: CP8 LOCAL SECRET READY
  (No output from config --quiet)
  api

WHAT CHANGES
- Docker Compose loads the API key from .secrets/api_key.txt as a file-backed
  read-only secret exposed at /run/secrets/api_key.
- AUTH_REQUIRED=true; APP_ENV=local for the pinned unpromoted synthetic model;
  API_KEY_FILE is set to the mounted secret path.
- Docker stays bound only to 127.0.0.1:8000.
- Health check uses /ready, verifying key configuration + loaded model.
- Nonroot user, read-only root and model mounts, dropped capabilities retained.
- Secret is not added to Docker image or passed as an environment variable.

SECURITY
- NEVER paste, screenshot, upload, or commit the secret file or its contents.
- The file remains a local plaintext secret, intended only for local testing.
- For real deployment use an external secret manager and TLS; this is NOT
  a production deployment.
- Do not change .env or share its contents.

STOP after the above commands. DO NOT REBUILD/RESTART DOCKER until the
Compose validation output has been reviewed; the current running CP7 container
will still serve without CP8 authentication until rebuilt/recreated.
