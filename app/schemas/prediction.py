"""Schemas for disease-risk predictions."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DiabetesInput(BaseModel):
    """Clinical measurements for the diabetes model. Leave optional ones empty if not measured."""

    model_config = ConfigDict(extra="forbid")

    glucose: float = Field(gt=0, le=400, description="Plasma glucose, 2 h OGTT (mg/dL)")
    bmi: float = Field(gt=0, le=80)
    age: int | None = Field(
        default=None, ge=0, le=130, description="Defaults to the patient's recorded age"
    )
    pregnancies: int | None = Field(default=None, ge=0, le=25)
    blood_pressure: float | None = Field(default=None, gt=0, le=200, description="Diastolic")
    skin_thickness: float | None = Field(default=None, gt=0, le=100)
    insulin: float | None = Field(default=None, gt=0, le=1000)
    diabetes_pedigree: float | None = Field(default=None, ge=0, le=3)


class ContributionOut(BaseModel):
    feature: str
    label: str
    value: float | None
    impact: float


class PredictionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    patient_id: int
    disease: str
    model_name: str
    model_version: str
    inputs: dict[str, Any]
    probability: float
    risk_level: str
    contributions: list[ContributionOut]
    created_at: datetime


class RiskSummary(BaseModel):
    disease: str
    low: int = 0
    moderate: int = 0
    high: int = 0
    patients_scored: int = 0


class ModelInfo(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    name: str
    version: str
    trained_at: str
    algorithm: str
    features: list[str]
    metrics: dict[str, float]
    decision_threshold: float
    risk_bands: list[dict[str, Any]]
    dataset: dict[str, Any]
