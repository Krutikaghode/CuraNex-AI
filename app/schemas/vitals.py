from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.monitoring.metrics import METRICS


class VitalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded_at: datetime | None = Field(default=None, description="Defaults to now (UTC)")
    glucose: float | None = None
    systolic_bp: float | None = None
    diastolic_bp: float | None = None
    heart_rate: float | None = None
    spo2: float | None = None
    temperature_c: float | None = None
    weight_kg: float | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("recorded_at")
    @classmethod
    def not_in_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        if value > datetime.now(UTC):
            raise ValueError("recorded_at cannot be in the future.")
        return value

    @model_validator(mode="after")
    def check_values(self) -> "VitalCreate":
        present = 0
        for key, metric in METRICS.items():
            value = getattr(self, key)
            if value is None:
                continue
            present += 1
            if not metric.valid_min <= value <= metric.valid_max:
                raise ValueError(
                    f"{metric.label} must be between {metric.valid_min:g} and "
                    f"{metric.valid_max:g} {metric.unit}."
                )
        if present == 0:
            raise ValueError("Provide at least one measurement.")
        if (
            self.systolic_bp is not None
            and self.diastolic_bp is not None
            and self.diastolic_bp >= self.systolic_bp
        ):
            raise ValueError("Diastolic BP must be lower than systolic BP.")
        return self


class VitalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    recorded_at: datetime
    glucose: float | None
    systolic_bp: float | None
    diastolic_bp: float | None
    heart_rate: float | None
    spo2: float | None
    temperature_c: float | None
    weight_kg: float | None
    notes: str | None
    source: str


class MetricSummaryOut(BaseModel):
    metric: str
    label: str
    unit: str
    readings: int
    latest: float | None
    latest_at: datetime | None
    reference_low: float | None
    reference_high: float | None
    status: str
    outlier: bool
    robust_z: float | None
    trend_per_30d: float | None
    trend_r2: float | None
    alerts: list[str]


class VitalsAnalysis(BaseModel):
    patient_id: int
    window_days: int
    readings: int
    alerts: list[str]
    metrics: list[MetricSummaryOut]


class PatientAlerts(BaseModel):
    patient_id: int
    full_name: str
    latest_reading_at: datetime
    alerts: list[str]


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int = Field(default=30, ge=7, le=180)
    profile: str = Field(default="worsening", pattern="^(stable|worsening)$")
