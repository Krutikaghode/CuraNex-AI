"""Load the trained diabetes model and score single patients with explanations."""

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import xgboost as xgb

from app.core.config import get_settings
from app.ml.features import FEATURES, ZERO_MEANS_MISSING, risk_level


class ModelNotAvailableError(RuntimeError):
    """Raised when the model artifact has not been trained or shipped."""


@dataclass(frozen=True)
class Contribution:
    feature: str
    value: float | None
    # SHAP contribution in log-odds; positive pushes risk up.
    impact: float


@dataclass(frozen=True)
class DiabetesPrediction:
    probability: float
    risk_level: str
    contributions: list[Contribution]


class DiabetesModel:
    def __init__(self, model_dir: Path):
        model_path, metadata_path = model_dir / "model.json", model_dir / "metadata.json"
        if not model_path.exists() or not metadata_path.exists():
            raise ModelNotAvailableError(
                f"No diabetes model in {model_dir}. Run: python -m app.ml.train_diabetes"
            )
        self.booster = xgb.Booster()
        self.booster.load_model(model_path)
        self.metadata: dict[str, Any] = json.loads(metadata_path.read_text())
        if self.metadata.get("features") != FEATURES:
            raise ModelNotAvailableError("Model features do not match app.ml.features.FEATURES.")

    @property
    def name(self) -> str:
        return self.metadata["name"]

    @property
    def version(self) -> str:
        return self.metadata["version"]

    def predict(self, inputs: dict[str, float | None]) -> DiabetesPrediction:
        row = []
        for feature in FEATURES:
            value = inputs.get(feature)
            if value is None or (feature in ZERO_MEANS_MISSING and value == 0):
                row.append(np.nan)
            else:
                row.append(float(value))
        matrix = xgb.DMatrix(np.array([row], dtype=float), feature_names=FEATURES, missing=np.nan)
        probability = float(self.booster.predict(matrix)[0])
        shap = self.booster.predict(matrix, pred_contribs=True)[0][:-1]  # last column is bias
        contributions = sorted(
            (
                Contribution(
                    feature=feature,
                    value=None if math.isnan(value) else value,
                    impact=round(float(impact), 4),
                )
                for feature, value, impact in zip(FEATURES, row, shap)
            ),
            key=lambda item: abs(item.impact),
            reverse=True,
        )
        return DiabetesPrediction(
            probability=round(probability, 4),
            risk_level=risk_level(probability),
            contributions=contributions,
        )


@lru_cache
def _load(model_dir: str) -> DiabetesModel:
    return DiabetesModel(Path(model_dir) / "diabetes")


def get_diabetes_model() -> DiabetesModel:
    """FastAPI dependency; cached after the first successful load."""
    return _load(get_settings().models_dir)
