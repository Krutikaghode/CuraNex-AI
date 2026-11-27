"""Vital-sign definitions and adult reference ranges (general guidance, not clinical advice)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    unit: str
    low: float | None  # below this is flagged
    high: float | None  # above this is flagged
    valid_min: float
    valid_max: float


METRICS: dict[str, Metric] = {
    m.key: m
    for m in [
        Metric("glucose", "Glucose", "mg/dL", 70, 140, 20, 600),
        Metric("systolic_bp", "Systolic BP", "mm Hg", 90, 130, 50, 260),
        Metric("diastolic_bp", "Diastolic BP", "mm Hg", 60, 85, 30, 160),
        Metric("heart_rate", "Heart rate", "bpm", 50, 100, 20, 250),
        Metric("spo2", "SpO2", "%", 94, None, 50, 100),
        Metric("temperature_c", "Temperature", "°C", 35.5, 37.8, 30, 44),
        Metric("weight_kg", "Weight", "kg", None, None, 1, 400),
    ]
}
