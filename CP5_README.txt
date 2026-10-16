Project 12 / CP5 Step 1: locked schema + registered-model inference

Extract this ZIP into the EXISTING 12_production_ml_mlops_platform folder.
Overwrite ONLY these 6 files:
 src/mlops_platform/config.py
 src/mlops_platform/schemas.py
 src/mlops_platform/serving/realtime.py
 src/mlops_platform/api/main.py
 tests/test_api.py
 tests/test_serving.py

DO NOT overwrite src/mlops_platform/registry/mlflow_utils.py or training/train.py.
Do not overwrite any MLflow database or previously generated artifact.

Run from the Project 12 root:
 .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q

Next checkpoint step after tests: invoke /predict against the real registered
model using a synthetic Project 9 test row and confirm numerical parity.
No server, deployment, cloud, retraining, or GitHub changes required yet.
