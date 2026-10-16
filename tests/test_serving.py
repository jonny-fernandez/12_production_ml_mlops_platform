"""CP6 unit checks: real-time and vectorized batch share one model source."""

import numpy as np
from mlops_platform.deployment.health import promotion_allowed
from mlops_platform.schemas import PredictionRequest
from mlops_platform.serving import realtime
from mlops_platform.serving.batch import predict_batch
from test_api import VALID


class FakeModel:
    def __init__(self):
        self.calls = 0

    def predict_proba(self, frame):
        self.calls += 1
        return np.tile(np.array([[0.8, 0.2]]), (len(frame), 1))


def test_batch_prediction_count(monkeypatch):
    model = FakeModel()
    monkeypatch.setattr(realtime, "_load_model", lambda: model)
    items = [PredictionRequest(features=VALID), PredictionRequest(features=VALID)]
    result = predict_batch(items)
    assert len(result) == 2
    assert all(item.prediction == 1 for item in result)
    assert model.calls == 1


def test_promotion_requires_all_gates():
    assert promotion_allowed(True, True, True)
    assert not promotion_allowed(True, False, True)
