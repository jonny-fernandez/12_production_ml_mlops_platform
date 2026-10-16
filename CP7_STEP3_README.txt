PROJECT 12 — CP7 STEP 3 — CONTAINER CONFIGURATION ONLY

1. Extract Dockerfile, docker-compose.yml and requirements-container.txt
   directly into the existing Project 12 root. Overwrite only the two
   existing Docker files; requirements-container.txt is new.

2. Keep the .dockerignore file created during the preceding CP7 step.
   It excludes .env, MLflow SQLite, data, and model artifacts from the image.

3. From the Project 12 root, inspect the Compose configuration:

       docker compose config --quiet
       docker compose config --services
       Test-Path requirements-container.txt
       Test-Path .dockerignore

   Expected: first command exits without an error; second prints 'api';
   both Test-Path commands return True.

DO NOT RUN docker compose build/up yet.

Important: the original MLflow registry contains Windows-local artifact URIs.
Simply mounting mlflow_tracking.db into Linux would not make those paths
resolvable. The next CP7 step will export a checksum-verified, read-only
copy of registered model version 1 and add a local bundle loader. The
registered model/version/approval status will remain unchanged.

Security: these files deliberately do not use env_file: .env, so real
local secrets are not injected into the container. The service binds
only to 127.0.0.1. The verified model will be mounted read-only, never
baked into the image. The image uses a non-root user and a read-only
root filesystem with writable /tmp only.

The base image is Python 3.12; the original Dockerfile used Python 3.11.
Container dependency pins mirror the tested Project 12 environment.
This is a local MLOps demonstration, not a production approval.
