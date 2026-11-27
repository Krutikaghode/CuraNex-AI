"""Feature definitions shared by training and inference for the diabetes model."""

FEATURES: list[str] = [
    "pregnancies",
    "glucose",
    "blood_pressure",
    "skin_thickness",
    "insulin",
    "bmi",
    "diabetes_pedigree",
    "age",
]
TARGET = "outcome"

# In the Pima data a zero in these columns means "not measured", not a real value.
ZERO_MEANS_MISSING: set[str] = {"glucose", "blood_pressure", "skin_thickness", "insulin", "bmi"}

FEATURE_LABELS: dict[str, str] = {
    "pregnancies": "Pregnancies",
    "glucose": "Glucose (mg/dL)",
    "blood_pressure": "Diastolic BP (mm Hg)",
    "skin_thickness": "Skin thickness (mm)",
    "insulin": "Insulin (mu U/mL)",
    "bmi": "BMI",
    "diabetes_pedigree": "Diabetes pedigree",
    "age": "Age",
}

# Probability cut-offs for the risk bands shown to users.
RISK_BANDS: list[tuple[float, str]] = [(0.3, "low"), (0.6, "moderate"), (1.01, "high")]


def risk_level(probability: float) -> str:
    for upper, label in RISK_BANDS:
        if probability < upper:
            return label
    return "high"
