Project 12 - CP6 Step 1 - Batch Inference

Only extract into your existing 12_production_ml_mlops_platform project root.
Preserve folders. Replace exactly the matching files below; the rest stay intact.

REPLACE:
  src/mlops_platform/schemas.py
  src/mlops_platform/api/main.py
  src/mlops_platform/serving/batch.py
  tests/test_serving.py

ADD:
  tests/test_batch.py

No changes to: training, MLflow registry, realtime.py, credentials, or model artifacts.

NEW ENDPOINT:
  POST /predict/batch
  Request: {"items": [{"features": {<all 19 Project 9 features>}}, ...]}
  Response: {"count": N, "predictions": [<same schema as /predict>, ...]}
  Batch size 1..1000, strict all-or-nothing validation, one pipeline call per batch.
  HTTP 422 for invalid requests; HTTP 503 for unavailable/bad model responses.

PowerShell, from project root:
  .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q

Send the test result before CP6 Step 2, which will check prediction parity
against actual registered MLflow version 1 on multiple test records.
