"""Train the diabetes risk model and write it plus its metadata to models/diabetes/.

Run from the repository root:  python -m app.ml.train_diabetes
Needs the dev requirements (scikit-learn, pandas) in addition to the API ones.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split

from app.ml.features import FEATURES, RISK_BANDS, TARGET, ZERO_MEANS_MISSING

SEED = 42
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = REPO_ROOT / "datasets" / "pima_diabetes.csv"
DEFAULT_OUT = REPO_ROOT / "models" / "diabetes"

PARAM_GRID = {
    "max_depth": [2, 3, 4],
    "n_estimators": [100, 200, 300],
    "learning_rate": [0.03, 0.05, 0.1],
}


def load_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = set(FEATURES + [TARGET]) - set(frame.columns)
    if missing:
        raise ValueError(f"Dataset is missing columns: {sorted(missing)}")
    for column in ZERO_MEANS_MISSING:
        frame[column] = frame[column].replace(0, np.nan)
    return frame


def train(data_path: Path, out_dir: Path) -> dict:
    frame = load_dataset(data_path)
    x, y = frame[FEATURES], frame[TARGET]
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, stratify=y, random_state=SEED
    )

    base = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        subsample=0.9,
        colsample_bytree=0.9,
        # Offsets the ~65/35 class imbalance so recall on positives is not sacrificed.
        scale_pos_weight=float((y_train == 0).sum() / (y_train == 1).sum()),
        random_state=SEED,
        n_jobs=1,
    )
    search = GridSearchCV(
        base,
        PARAM_GRID,
        scoring="roc_auc",
        cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED),
        n_jobs=-1,
    )
    search.fit(x_train, y_train)
    model: xgb.XGBClassifier = search.best_estimator_

    probabilities = model.predict_proba(x_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics = {
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions)), 4),
        "recall": round(float(recall_score(y_test, predictions)), 4),
        "f1": round(float(f1_score(y_test, predictions)), 4),
        "cv_roc_auc": round(float(search.best_score_), 4),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    model.get_booster().save_model(out_dir / "model.json")
    trained_at = datetime.now(UTC)
    metadata = {
        "name": "diabetes-xgboost",
        "version": trained_at.strftime("%Y%m%d%H%M%S"),
        "trained_at": trained_at.isoformat(timespec="seconds"),
        "algorithm": f"XGBoost {xgb.__version__}",
        "features": FEATURES,
        "best_params": search.best_params_,
        "metrics": metrics,
        "decision_threshold": 0.5,
        "risk_bands": [{"below": upper, "level": label} for upper, label in RISK_BANDS],
        "dataset": {
            "file": data_path.name,
            "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
            "rows": int(len(frame)),
            "train_rows": int(len(x_train)),
            "test_rows": int(len(x_test)),
            "positive_rate": round(float(y.mean()), 4),
        },
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    metadata = train(args.data, args.out)
    print(json.dumps({"best_params": metadata["best_params"], **metadata["metrics"]}, indent=2))


if __name__ == "__main__":
    main()
