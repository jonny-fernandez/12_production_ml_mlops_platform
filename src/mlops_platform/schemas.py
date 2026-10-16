"""Locked Project 9 / Project 12 real-time prediction contract (CP5).

All 19 source features are required. Reject extras and unsafe coercion;
observed training ranges are not used as arbitrary request limits.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


PositiveInt = Annotated[int, Field(strict=True, ge=0)]
PositiveFloat = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
FiniteFloat = Annotated[float, Field(strict=True, allow_inf_nan=False)]
RatioFloat = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]


class AttritionFeatures(BaseModel):
    """19 features in the identical order of Project 9's trained pipeline."""

    model_config = ConfigDict(extra="forbid", strict=True)

    department: Literal[
        "Development", "Finance", "Operations", "People", "Programs", "Research"
    ]
    job_family: Literal[
        "Data", "Finance", "Fundraising", "HR", "Operations", "Program Delivery"
    ]
    job_level: Literal["L1", "L2", "L3", "L4"]
    location: Literal[
        "Chicago-Downtown", "Chicago-North", "Chicago-South", "Remote-US"
    ]
    employment_type: Literal["Full-Time", "Part-Time"]

    age: Annotated[int, Field(strict=True, ge=1)]
    tenure_months: PositiveInt
    monthly_salary_annualized: PositiveFloat
    overtime_hours_90d: PositiveFloat
    absences_90d: PositiveInt
    performance_score: PositiveFloat
    engagement_score: PositiveFloat
    manager_changes_12m: PositiveInt
    months_since_promotion: PositiveInt
    commute_minutes: PositiveInt
    training_hours_12m: PositiveFloat
    remote_work_ratio: RatioFloat
    salary_change_pct_12m: FiniteFloat
    internal_moves_24m: PositiveInt


FEATURE_NAMES = tuple(AttritionFeatures.model_fields)


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    features: AttritionFeatures


class PredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prediction: Literal[0, 1]
    probability: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    model_name: str
    model_version: str

# CP6: Each record uses the locked CP5 schema. All-or-nothing validation prevents
# partial inference and avoids silent dropping or reordering of rejected rows.
MAX_BATCH_SIZE = 1000  # Agrees with configs/model.yaml -> serving.max_batch_size


class BatchPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    items: Annotated[list[PredictionRequest], Field(min_length=1, max_length=MAX_BATCH_SIZE)]


class BatchPredictionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(ge=0)
    predictions: list[PredictionResponse]
