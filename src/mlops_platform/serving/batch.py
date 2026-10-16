"""CP6: vectorized local batch inference using the *same* CP5 registry model.

This module does not register, retrain, promote, or modify model artifacts.
Validated items are processed in input order; an invalid model result fails the
entire batch rather than returning partial or fabricated predictions.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from mlops_platform.schemas import (
    FEATURE_NAMES,
    MAX_BATCH_SIZE,
    PredictionRequest,
    PredictionResponse,
)
from mlops_platform.serving import realtime


def predict_batch(items: list[PredictionRequest]) -> list[PredictionResponse]:
    """Run one predict_proba call for an ordered, validated batch.

    The HTTP endpoint requires at least one row. The Python function retains
    the starter's behavior of returning [] for an empty list.
    """
    if not items:
        return []
    if len(items) > MAX_BATCH_SIZE:
        raise ValueError(f"Batch exceeds {MAX_BATCH_SIZE} items")
    if not all(isinstance(item, PredictionRequest) for item in items):
        raise TypeError("Batch items must be validated PredictionRequest instances")

    model = realtime._load_model()  # Same provenance and environment gates as CP5
    frame = pd.DataFrame.from_records(
        [item.features.model_dump() for item in items], columns=list(FEATURE_NAMES)
    )
    try:
        probabilities = np.asarray(model.predict_proba(frame), dtype=float)
    except Exception as exc:
        raise realtime.ModelUnavailableError("Batch model inference failed") from exc

    if probabilities.shape != (len(items), 2):
        raise realtime.ModelUnavailableError("Unexpected batch probability shape")
    if not np.isfinite(probabilities).all():
        raise realtime.ModelUnavailableError("Non-finite probability in batch result")
    if (probabilities < 0).any() or (probabilities > 1).any():
        raise realtime.ModelUnavailableError("Out-of-range probability in batch result")
    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-6, rtol=0):
        raise realtime.ModelUnavailableError("Invalid probability distribution")

    return [
        PredictionResponse(
            prediction=int(float(row[1]) >= realtime.EXPECTED_THRESHOLD),
            probability=float(row[1]),
            model_name=realtime.EXPECTED_NAME,
            model_version=realtime.EXPECTED_VERSION,
        )
        for row in probabilities
    ]
