"""Turn a patient's vitals history into flags, outliers and trends.

Three independent signals per metric:
  * range     - latest value outside the reference range in metrics.py
  * outlier   - latest value far from this patient's own baseline (robust z-score using the
                median and MAD of earlier readings), which catches changes that are still
                "in range" but unusual for the person
  * trend     - least-squares slope per 30 days over the analysis window, with R²
"""

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from app.monitoring.metrics import METRICS

MIN_BASELINE = 5  # readings needed before outlier detection is meaningful
OUTLIER_Z = 3.5  # Iglewicz-Hoaglin cut-off for modified z-scores
MIN_TREND_POINTS = 4
SECONDS_PER_30_DAYS = 30 * 24 * 3600


@dataclass
class MetricSummary:
    metric: str
    label: str
    unit: str
    readings: int
    latest: float | None = None
    latest_at: datetime | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    status: str = "no-data"  # no-data | normal | low | high
    outlier: bool = False
    robust_z: float | None = None
    trend_per_30d: float | None = None
    trend_r2: float | None = None
    alerts: list[str] = field(default_factory=list)


def _robust_z(history: np.ndarray, value: float) -> float | None:
    median = float(np.median(history))
    mad = float(np.median(np.abs(history - median)))
    if mad == 0:
        return None
    return 0.6745 * (value - median) / mad


def _trend(times: np.ndarray, values: np.ndarray) -> tuple[float, float] | None:
    if len(values) < MIN_TREND_POINTS or np.ptp(times) == 0:
        return None
    x = (times - times[0]) / SECONDS_PER_30_DAYS
    slope, intercept = np.polyfit(x, values, 1)
    fitted = slope * x + intercept
    total = float(np.sum((values - values.mean()) ** 2))
    r2 = 1.0 - float(np.sum((values - fitted) ** 2)) / total if total else 0.0
    return float(slope), r2


def summarize(readings: list) -> list[MetricSummary]:
    """readings: VitalReading-like objects ordered by recorded_at ascending."""
    summaries = []
    for key, metric in METRICS.items():
        points = [(r.recorded_at, getattr(r, key)) for r in readings if getattr(r, key) is not None]
        summary = MetricSummary(
            metric=key,
            label=metric.label,
            unit=metric.unit,
            readings=len(points),
            reference_low=metric.low,
            reference_high=metric.high,
        )
        if points:
            times = np.array([t.timestamp() for t, _ in points], dtype=float)
            values = np.array([v for _, v in points], dtype=float)
            summary.latest, summary.latest_at = float(values[-1]), points[-1][0]

            if metric.low is not None and summary.latest < metric.low:
                summary.status = "low"
                summary.alerts.append(
                    f"{metric.label} {summary.latest:g} {metric.unit} is below {metric.low:g}."
                )
            elif metric.high is not None and summary.latest > metric.high:
                summary.status = "high"
                summary.alerts.append(
                    f"{metric.label} {summary.latest:g} {metric.unit} is above {metric.high:g}."
                )
            else:
                summary.status = "normal"

            if len(values) > MIN_BASELINE:
                z = _robust_z(values[:-1], summary.latest)
                if z is not None:
                    summary.robust_z = round(z, 2)
                    if abs(z) >= OUTLIER_Z:
                        summary.outlier = True
                        direction = "higher" if z > 0 else "lower"
                        summary.alerts.append(
                            f"{metric.label} is unusually {direction} than this patient's baseline."
                        )

            trend = _trend(times, values)
            if trend:
                summary.trend_per_30d, summary.trend_r2 = round(trend[0], 3), round(trend[1], 3)
        summaries.append(summary)
    return summaries
