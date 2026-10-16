"""Project 12 API: validated inference with CP8 auth, readiness and safe logs."""

from fastapi import Depends, FastAPI, HTTPException

from mlops_platform.api.observability import request_audit_middleware
from mlops_platform.api.security import authentication_ready, require_api_key
from mlops_platform.config import settings
from mlops_platform.schemas import (
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionRequest,
    PredictionResponse,
)
from mlops_platform.serving.batch import predict_batch
from mlops_platform.serving import realtime
from mlops_platform.serving.realtime import ModelUnavailableError, predict_one

app = FastAPI(title="Production ML & MLOps Platform", version="0.1.0")
app.middleware("http")(request_audit_middleware)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness: this process can answer HTTP, not proof of model readiness."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness: valid security config AND successfully loaded pinned model."""
    if not authentication_ready():
        raise HTTPException(status_code=503, detail="Service not ready")
    try:
        realtime._load_model()
    except Exception as exc:
        # Do not expose local paths, registry errors, or sensitive configuration.
        raise HTTPException(status_code=503, detail="Service not ready") from exc
    return {"status": "ready"}


@app.get("/model/info", dependencies=[Depends(require_api_key)])
def model_info() -> dict[str, str]:
    return {"model_name": settings.model_name, "model_version": settings.model_version}


@app.post("/predict", response_model=PredictionResponse, dependencies=[Depends(require_api_key)])
def predict(payload: PredictionRequest) -> PredictionResponse:
    try:
        return predict_one(payload)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Registered model unavailable") from exc


@app.post("/predict/batch", response_model=BatchPredictionResponse, dependencies=[Depends(require_api_key)])
def predict_batch_endpoint(payload: BatchPredictionRequest) -> BatchPredictionResponse:
    """All-or-nothing batch inference, preserving input order (1..1000)."""
    try:
        results = predict_batch(payload.items)
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail="Registered model unavailable") from exc
    return BatchPredictionResponse(count=len(results), predictions=results)
