PROJECT 12 -- CP8 Step 6: Privacy-Safe Docker Logs

1. Extract this ZIP into the root of your existing 12_production_ml_mlops_platform folder.
   Overwrite Dockerfile only; place CP8_docker_log_privacy_check.py beside it.
   Do not overwrite .env, docker-compose.yml or any model files.

2. Rebuild the local API container from PowerShell in your project folder:
   docker compose up -d --build --force-recreate api

3. Wait for Docker to reach healthy status (docker compose ps).

4. Audit HTTP logs without exposing keys:
   .\.venv\Scripts\python.exe .\CP8_docker_log_privacy_check.py

5. Run the existing CP8 prediction-parity test after the audit:
   .\.venv\Scripts\python.exe .\Project12_CP8_docker_auth_http_check.py

NOTES:
- Dockerfile retains the CP7 model container setup but disables Uvicorn
  default access logs. The application's own privacy-safe JSON logs remain.
- Never paste your .env or .secrets/api_key.txt into chat.
- This is local container validation, not a production deployment.
