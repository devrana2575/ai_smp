"""Chronological walk-forward evaluation for the stock prediction models.

This module is deliberately separate from the production training and
inference paths.  It builds an evaluation-only dataset, reserves a final
holdout, compares the five existing algorithms with a naive persistence
baseline and the existing equal-weight ensemble, and writes a JSON report.

Key safeguards
--------------
* No shuffling: folds are created from the chronological row order.
* Expanding windows: each fold's training prefix grows over time.
* No target leakage: a training row's target date must be earlier than the
  validation target period's first target date.
* Per-fold preprocessing: each SVR model instance fits a fresh scaler only on
  that fold's training rows.
* Final holdout isolation: the holdout is created before model selection and
  is never used to choose a model, tune a parameter, or assign weights.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.config import settings
from app.models.decision_tree import DecisionTreeModel
from app.models.linear_regression import LinearRegressionModel
from app.models.random_forest import RandomForestModel
from app.models.svr_model import SVRModel
from app.models.xgboost_model import XGBoostModel
from app.services.data_service import data_service, validate_symbol
from app.services.evaluation_metrics import (
    calculate_metrics,
    compare_metrics_to_baseline,
)
from app.services.feature_engineering import feature_engineering


MODEL_NAMES: Tuple[str, ...] = (
    "linear_regression",
    "decision_tree",
    "random_forest",
    "svr",
    "xgboost",
)
BASELINE_NAME = "naive_persistence"
ENSEMBLE_NAME = "ensemble_equal_weight"
ALL_CANDIDATE_NAMES: Tuple[str, ...] = MODEL_NAMES + (
    BASELINE_NAME,
    ENSEMBLE_NAME,
)

MODEL_LABELS: Dict[str, str] = {
    "linear_regression": "Linear Regression",
    "decision_tree": "Decision Tree",
    "random_forest": "Random Forest",
    "svr": "Support Vector Regressor (SVR)",
    "xgboost": "XGBoost",
    BASELINE_NAME: "Naive Persistence (current close)",
    ENSEMBLE_NAME: "Equal-Weight Ensemble",
}

MODEL_FACTORIES: Dict[str, Callable[[], Any]] = {
    "linear_regression": LinearRegressionModel,
    "decision_tree": DecisionTreeModel,
    "random_forest": RandomForestModel,
    "svr": SVRModel,
    "xgboost": XGBoostModel,
}


class InsufficientEvaluationData(ValueError):
    """Raised when there is not enough history for a reliable evaluation."""


@dataclass(frozen=True)
class EvaluationConfig:
    """Configurable evaluation settings.

    The defaults are intentionally separate from production training so a
    longer history can be used for evaluation without changing saved models or
    inference behavior.
    """

    period: str = "2y"
    folds: int = 5
    holdout_fraction: float = 0.2
    min_train_samples: int = 60
    min_validation_samples: int = 10
    min_holdout_samples: int = 10
    initial_train_fraction: float = 0.5
    selection_metric: str = "rmse"
    random_state: int = 42

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.period, str) or not self.period.strip():
            raise ValueError("period must be a non-empty string")
        if not isinstance(self.folds, int) or self.folds < 2:
            raise ValueError("folds must be an integer of at least 2")
        if not 0.0 < self.holdout_fraction < 1.0:
            raise ValueError("holdout_fraction must be between 0 and 1")
        if self.min_train_samples < 2:
            raise ValueError("min_train_samples must be at least 2")
        if self.min_validation_samples < 1:
            raise ValueError("min_validation_samples must be at least 1")
        if self.min_holdout_samples < 1:
            raise ValueError("min_holdout_samples must be at least 1")
        if not 0.0 < self.initial_train_fraction < 1.0:
            raise ValueError("initial_train_fraction must be between 0 and 1")
        if self.selection_metric not in {"rmse", "mae"}:
            raise ValueError("selection_metric must be 'rmse' or 'mae'")
        if not isinstance(self.random_state, int):
            raise ValueError("random_state must be an integer")

    @classmethod
    def from_settings(cls) -> "EvaluationConfig":
        return cls(
            period=settings.EVALUATION_PERIOD,
            folds=settings.EVALUATION_FOLDS,
            holdout_fraction=settings.EVALUATION_HOLDOUT_FRACTION,
            min_train_samples=settings.EVALUATION_MIN_TRAIN_SAMPLES,
            min_validation_samples=settings.EVALUATION_MIN_VALIDATION_SAMPLES,
            min_holdout_samples=settings.EVALUATION_MIN_HOLDOUT_SAMPLES,
            initial_train_fraction=settings.EVALUATION_INITIAL_TRAIN_FRACTION,
            selection_metric="rmse",
            random_state=settings.RANDOM_STATE,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "period": self.period,
            "folds_requested": self.folds,
            "holdout_fraction": self.holdout_fraction,
            "min_train_samples": self.min_train_samples,
            "min_validation_samples": self.min_validation_samples,
            "min_holdout_samples": self.min_holdout_samples,
            "initial_train_fraction": self.initial_train_fraction,
            "selection_metric": self.selection_metric,
            "random_state": self.random_state,
        }


@dataclass
class EvaluationDataset:
    """Evaluation-only dataset with feature and target dates."""

    clean_df: pd.DataFrame
    featured_df: pd.DataFrame
    feature_columns: List[str]
    data_fingerprint: str


@dataclass
class WalkForwardFold:
    """Index ranges and dates for one chronological validation fold."""

    fold: int
    train_indices: np.ndarray
    validation_indices: np.ndarray
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    train_target_start: pd.Timestamp
    train_target_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    validation_target_start: pd.Timestamp
    validation_target_end: pd.Timestamp


def _iso_date(value: Any) -> Optional[str]:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def _json_safe(value: Any) -> Any:
    """Convert numpy/pandas values and non-finite floats to JSON-safe values."""

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
        return value if math.isfinite(value) else None
    if isinstance(value, (float,)):
        return value if math.isfinite(value) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        return _iso_date(value)
    if value is pd.NaT:
        return None
    return value


def _data_fingerprint(clean_df: pd.DataFrame) -> str:
    frame = clean_df.copy()
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.strftime("%Y-%m-%d")
    payload = frame[
        ["Date", "Open", "High", "Low", "Close", "Volume"]
    ].to_csv(index=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_evaluation_dataset(
    clean_df: pd.DataFrame,
    feature_engineering_service=feature_engineering,
) -> EvaluationDataset:
    """Build causal features plus aligned feature and target dates."""

    if not isinstance(clean_df, pd.DataFrame) or clean_df.empty:
        raise InsufficientEvaluationData("No stock data is available for evaluation")

    required = ["Date", "Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required if column not in clean_df.columns]
    if missing:
        raise ValueError(
            "Evaluation data is missing required columns: " + ", ".join(missing)
        )

    clean = clean_df.copy()
    clean["Date"] = pd.to_datetime(clean["Date"]).dt.tz_localize(None)
    clean = (
        clean.sort_values("Date")
        .drop_duplicates(subset=["Date"])
        .reset_index(drop=True)
    )

    if len(clean) < feature_engineering_service.MIN_HISTORY_ROWS + 2:
        raise InsufficientEvaluationData(
            "Not enough historical rows for evaluation: received "
            f"{len(clean)}, need more than "
            f"{feature_engineering_service.MIN_HISTORY_ROWS + 1}"
        )

    # The feature transform is causal.  It uses only the current row and
    # earlier rows to build indicators and adds Next_Day_Close as the target.
    featured = feature_engineering_service.transform(clean)
    featured["Date"] = pd.to_datetime(featured["Date"]).dt.tz_localize(None)

    date_to_next: Dict[pd.Timestamp, pd.Timestamp] = {}
    dates = list(pd.to_datetime(clean["Date"]))
    for current_date, next_date in zip(dates, dates[1:]):
        date_to_next[current_date] = next_date
    date_to_open = {
        pd.Timestamp(date): float(open_price)
        for date, open_price in zip(dates, clean["Open"].tolist())
    }
    featured["Target_Date"] = featured["Date"].map(date_to_next)
    featured["Next_Day_Open"] = featured["Target_Date"].map(date_to_open)
    featured = featured.dropna(subset=["Target_Date"]).reset_index(drop=True)
    featured["Target_Date"] = pd.to_datetime(featured["Target_Date"])
    if not np.all(np.isfinite(featured["Next_Day_Open"].to_numpy(dtype=float))):
        raise ValueError(
            "Evaluation data is missing a finite next-session open price"
        )

    if featured.empty:
        raise InsufficientEvaluationData(
            "No complete feature/target rows remain after feature engineering"
        )

    feature_columns = list(feature_engineering_service.get_feature_columns())
    missing_features = [
        column for column in feature_columns if column not in featured.columns
    ]
    if missing_features:
        raise ValueError(
            "Evaluation feature columns are missing from the transformed data: "
            + ", ".join(missing_features)
        )

    feature_values = featured[feature_columns].to_numpy(dtype=float)
    target_values = featured["Next_Day_Close"].to_numpy(dtype=float)
    if not np.all(np.isfinite(feature_values)):
        raise ValueError("Evaluation feature data contains non-finite values")
    if not np.all(np.isfinite(target_values)):
        raise ValueError("Evaluation target data contains non-finite values")

    if not featured["Date"].is_monotonic_increasing:
        raise ValueError("Feature dates are not in chronological order")
    if not featured["Target_Date"].is_monotonic_increasing:
        raise ValueError("Target dates are not in chronological order")
    if featured["Target_Date"].duplicated().any():
        raise ValueError("Target dates must be unique")
    if not (featured["Target_Date"] > featured["Date"]).all():
        raise ValueError("Every target date must be after its feature date")

    return EvaluationDataset(
        clean_df=clean,
        featured_df=featured,
        feature_columns=feature_columns,
        data_fingerprint=_data_fingerprint(clean),
    )


def split_development_holdout(
    dataset: EvaluationDataset,
    config: EvaluationConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Reserve the most recent chronological target rows as final holdout."""

    featured = dataset.featured_df.reset_index(drop=True)
    total_rows = len(featured)

    # Ensure the earlier development period can support the requested folds
    # and the holdout has a meaningful minimum size.
    min_development_rows = (
        config.min_train_samples
        + config.folds * config.min_validation_samples
    )
    if total_rows < min_development_rows + config.min_holdout_samples:
        raise InsufficientEvaluationData(
            "Not enough feature/target rows for a walk-forward evaluation "
            f"with {config.folds} folds and a final holdout: received "
            f"{total_rows}, need at least "
            f"{min_development_rows + config.min_holdout_samples}. "
            "Use a longer period or reduce the fold/minimum-sample settings."
        )

    requested_holdout = max(
        config.min_holdout_samples,
        int(math.ceil(total_rows * config.holdout_fraction)),
    )
    max_holdout = total_rows - min_development_rows
    actual_holdout = min(requested_holdout, max_holdout)
    if actual_holdout < config.min_holdout_samples:
        raise InsufficientEvaluationData(
            "Not enough rows remain for the final holdout after reserving "
            f"development data: {actual_holdout} < "
            f"{config.min_holdout_samples}"
        )

    holdout_start = total_rows - actual_holdout
    development = featured.iloc[:holdout_start].reset_index(drop=True)
    holdout = featured.iloc[holdout_start:].reset_index(drop=True)

    if development.empty or holdout.empty:
        raise InsufficientEvaluationData(
            "The chronological holdout split produced an empty period"
        )
    if not (
        holdout["Target_Date"].iloc[0]
        > development["Target_Date"].iloc[-1]
    ):
        raise ValueError("Holdout target dates must follow development targets")

    info = {
        "total_feature_target_rows": total_rows,
        "development_rows": len(development),
        "holdout_rows": len(holdout),
        "holdout_start_index": int(holdout_start),
        "holdout_end_index": int(total_rows - 1),
        "requested_holdout_fraction": config.holdout_fraction,
        "requested_holdout_samples": int(requested_holdout),
        "actual_holdout_fraction": round(len(holdout) / total_rows, 6),
        "actual_holdout_samples": int(actual_holdout),
        "holdout_size_adjusted": bool(actual_holdout != requested_holdout),
    }
    return development, holdout, info


def generate_walk_forward_folds(
    development: pd.DataFrame,
    config: EvaluationConfig,
) -> Tuple[List[WalkForwardFold], Dict[str, Any]]:
    """Create contiguous, non-overlapping expanding-window folds.

    Training rows are those whose target date is earlier than the first
    validation target date.  Validation rows are chronological and are never
    shuffled.  The number of folds is reduced only when the available data
    cannot support the requested count with the configured minimum validation
    size; the reduction is recorded in the returned metadata.
    """

    if "Target_Date" not in development.columns:
        raise ValueError("development data must contain Target_Date")
    if not development["Target_Date"].is_monotonic_increasing:
        raise ValueError("development target dates must be chronological")

    total_rows = len(development)
    min_required = (
        config.min_train_samples + 2 * config.min_validation_samples
    )
    if total_rows < min_required:
        raise InsufficientEvaluationData(
            "Not enough development rows for at least two walk-forward folds: "
            f"received {total_rows}, need at least {min_required}"
        )

    initial_start = max(
        config.min_train_samples,
        int(math.ceil(total_rows * config.initial_train_fraction)),
    )

    def _max_folds_for_start(start: int) -> int:
        return (total_rows - start) // config.min_validation_samples

    if _max_folds_for_start(initial_start) < 2:
        # If the configured initial fraction is too aggressive for this
        # history, fall back to the minimum training size rather than silently
        # producing a single, unreliable fold.
        if _max_folds_for_start(config.min_train_samples) >= 2:
            initial_start = config.min_train_samples
        else:
            raise InsufficientEvaluationData(
                "Not enough development rows after the minimum training "
                "period to create at least two validation folds"
            )

    max_folds = _max_folds_for_start(initial_start)
    folds_used = min(config.folds, max_folds)
    if folds_used < 2:
        raise InsufficientEvaluationData(
            "Not enough development rows to create at least two validation "
            "folds with the configured minimum validation size"
        )

    available_validation_rows = total_rows - initial_start
    fold_size = available_validation_rows // folds_used
    if fold_size < config.min_validation_samples:
        raise InsufficientEvaluationData(
            "Not enough rows for each validation fold: "
            f"fold size {fold_size} < {config.min_validation_samples}"
        )

    target_dates = development["Target_Date"].reset_index(drop=True)
    feature_dates = development["Date"].reset_index(drop=True)

    folds: List[WalkForwardFold] = []
    previous_validation_end = -1
    previous_train_end = -1

    for fold_number in range(1, folds_used + 1):
        index = fold_number - 1
        validation_start_index = initial_start + index * fold_size
        if fold_number == folds_used:
            validation_end_index = total_rows
        else:
            validation_end_index = validation_start_index + fold_size

        if validation_end_index - validation_start_index < (
            config.min_validation_samples
        ):
            raise InsufficientEvaluationData(
                f"Fold {fold_number} has too few validation rows"
            )
        if validation_start_index < previous_validation_end:
            raise ValueError("Walk-forward validation folds overlap")
        if validation_start_index >= validation_end_index:
            raise ValueError("Walk-forward validation fold is empty")

        validation_target_start = target_dates.iloc[validation_start_index]
        train_mask = target_dates < validation_target_start
        train_end = int(np.count_nonzero(train_mask.to_numpy()))
        if train_end > validation_start_index:
            raise ValueError(
                "Training rows overlap the validation feature period"
            )
        if train_end < config.min_train_samples:
            raise InsufficientEvaluationData(
                f"Fold {fold_number} has only {train_end} training rows; "
                f"at least {config.min_train_samples} are required"
            )
        if train_end <= previous_train_end:
            raise ValueError("Training windows must expand between folds")
        if train_end == 0 or not bool(train_mask.iloc[:train_end].all()):
            raise ValueError("Training rows must form a contiguous prefix")

        train_indices = np.arange(0, train_end, dtype=int)
        validation_indices = np.arange(
            validation_start_index, validation_end_index, dtype=int
        )

        train_start = pd.Timestamp(feature_dates.iloc[0])
        train_end_date = pd.Timestamp(feature_dates.iloc[train_end - 1])
        train_target_start = pd.Timestamp(target_dates.iloc[0])
        train_target_end = pd.Timestamp(target_dates.iloc[train_end - 1])
        validation_start = pd.Timestamp(
            feature_dates.iloc[validation_start_index]
        )
        validation_end = pd.Timestamp(
            feature_dates.iloc[validation_end_index - 1]
        )
        validation_target_start = pd.Timestamp(
            target_dates.iloc[validation_start_index]
        )
        validation_target_end = pd.Timestamp(
            target_dates.iloc[validation_end_index - 1]
        )

        if not train_end_date < validation_start:
            raise ValueError(
                f"Fold {fold_number} training features are not earlier than "
                "its validation features"
            )
        if not train_target_end < validation_target_start:
            raise ValueError(
                f"Fold {fold_number} training targets are not earlier than "
                "its validation targets"
            )
        if not validation_target_start > validation_start:
            raise ValueError(
                f"Fold {fold_number} validation target is not in the future"
            )

        folds.append(
            WalkForwardFold(
                fold=fold_number,
                train_indices=train_indices,
                validation_indices=validation_indices,
                train_start=train_start,
                train_end=train_end_date,
                train_target_start=train_target_start,
                train_target_end=train_target_end,
                validation_start=validation_start,
                validation_end=validation_end,
                validation_target_start=validation_target_start,
                validation_target_end=validation_target_end,
            )
        )
        previous_validation_end = validation_end_index
        previous_train_end = train_end

    metadata = {
        "requested_folds": config.folds,
        "folds_used": folds_used,
        "folds_reduced": folds_used < config.folds,
        "development_rows": total_rows,
        "initial_validation_start_index": initial_start,
        "initial_validation_start_date": _iso_date(
            feature_dates.iloc[initial_start]
        ),
        "available_validation_rows": available_validation_rows,
        "fold_size": fold_size,
        "last_fold_extra_rows": available_validation_rows
        - (fold_size * folds_used),
    }
    return folds, metadata


def _fold_train_metadata(
    development: pd.DataFrame,
    train_indices: np.ndarray,
) -> Dict[str, Any]:
    train = development.iloc[train_indices]
    return {
        "samples": int(len(train)),
        "start": _iso_date(train["Date"].iloc[0]),
        "end": _iso_date(train["Date"].iloc[-1]),
        "target_start": _iso_date(train["Target_Date"].iloc[0]),
        "target_end": _iso_date(train["Target_Date"].iloc[-1]),
    }


def _validation_metadata(
    validation: pd.DataFrame,
    predictions: Mapping[str, Optional[np.ndarray]],
) -> Dict[str, Any]:
    return {
        "samples": int(len(validation)),
        "start": _iso_date(validation["Date"].iloc[0]),
        "end": _iso_date(validation["Date"].iloc[-1]),
        "target_start": _iso_date(validation["Target_Date"].iloc[0]),
        "target_end": _iso_date(validation["Target_Date"].iloc[-1]),
        "dates": [_iso_date(value) for value in validation["Date"].tolist()],
        "target_dates": [
            _iso_date(value) for value in validation["Target_Date"].tolist()
        ],
        "current_close": [
            float(value) for value in validation["Close"].tolist()
        ],
        "actual_next_open": [
            float(value) for value in validation["Next_Day_Open"].tolist()
        ],
        "actual_next_close": [
            float(value)
            for value in validation["Next_Day_Close"].tolist()
        ],
        "predictions": {
            name: [float(value) for value in prediction.tolist()]
            for name, prediction in predictions.items()
            if prediction is not None
        },
    }


def _model_fit_diagnostics(
    name: str,
    model: Any,
    train_samples: int,
    train_features: int,
    feature_columns: Sequence[str],
) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {
        "status": "ok",
        "train_samples": int(train_samples),
        "train_features": int(train_features),
    }
    if name == "svr":
        scaler = getattr(model, "scaler", None)
        if scaler is not None and hasattr(scaler, "mean_"):
            diagnostics["preprocessing"] = {
                "name": "StandardScaler",
                "fit_on": "fold_training_data_only",
                "fit_samples": int(train_samples),
                "feature_columns": list(feature_columns),
                "feature_means": [
                    round(float(value), 6)
                    for value in np.asarray(scaler.mean_).reshape(-1)
                ],
            }
    return diagnostics


def _fit_models_for_fold(
    model_factories: Mapping[str, Callable[[], Any]],
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_validation: np.ndarray,
    validation: pd.DataFrame,
    feature_columns: Sequence[str],
) -> Tuple[
    Dict[str, Optional[np.ndarray]],
    Dict[str, Dict[str, Any]],
]:
    """Fit fresh model instances and return predictions plus diagnostics."""

    predictions: Dict[str, Optional[np.ndarray]] = {}
    diagnostics: Dict[str, Dict[str, Any]] = {}

    for name in MODEL_NAMES:
        factory = model_factories.get(name)
        if factory is None:
            predictions[name] = None
            diagnostics[name] = {
                "status": "failed",
                "error": f"No model factory registered for {name}",
                "train_samples": int(X_train.shape[0]),
                "train_features": int(X_train.shape[1]),
            }
            continue

        try:
            model = factory()
            model.train(X_train, y_train)
            raw_prediction = model.predict(X_validation)
            prediction = np.asarray(raw_prediction, dtype=float).reshape(-1)
            if len(prediction) != len(validation):
                raise ValueError(
                    f"Model {name} returned {len(prediction)} predictions for "
                    f"{len(validation)} validation rows"
                )
            if not np.all(np.isfinite(prediction)):
                raise ValueError(f"Model {name} returned non-finite predictions")

            predictions[name] = prediction
            diagnostics[name] = _model_fit_diagnostics(
                name=name,
                model=model,
                train_samples=int(X_train.shape[0]),
                train_features=int(X_train.shape[1]),
                feature_columns=feature_columns,
            )
        except Exception as exc:  # noqa: BLE001 - failures are reported, not hidden
            predictions[name] = None
            diagnostics[name] = {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "train_samples": int(X_train.shape[0]),
                "train_features": int(X_train.shape[1]),
            }

    return predictions, diagnostics


def _evaluate_rows(
    model_factories: Mapping[str, Callable[[], Any]],
    train: pd.DataFrame,
    validation: pd.DataFrame,
    feature_columns: Sequence[str],
    label: str,
) -> Dict[str, Any]:
    """Fit and evaluate all candidates on one chronological split."""

    X_train = train[list(feature_columns)].to_numpy(dtype=float)
    y_train = train["Next_Day_Close"].to_numpy(dtype=float)
    X_validation = validation[list(feature_columns)].to_numpy(dtype=float)
    y_validation = validation["Next_Day_Close"].to_numpy(dtype=float)
    current_close = validation["Close"].to_numpy(dtype=float)
    close_index = list(feature_columns).index("Close")

    model_predictions, model_diagnostics = _fit_models_for_fold(
        model_factories=model_factories,
        X_train=X_train,
        y_train=y_train,
        X_validation=X_validation,
        validation=validation,
        feature_columns=feature_columns,
    )

    # The naive baseline uses exactly the same validation rows and targets as
    # every ML model.  Its prediction is the current-day close.
    baseline_prediction = X_validation[:, close_index].copy()
    predictions: Dict[str, Optional[np.ndarray]] = dict(model_predictions)
    predictions[BASELINE_NAME] = baseline_prediction

    component_predictions = [model_predictions[name] for name in MODEL_NAMES]
    if all(prediction is not None for prediction in component_predictions):
        ensemble_prediction = np.mean(
            np.vstack(component_predictions), axis=0
        )
        predictions[ENSEMBLE_NAME] = ensemble_prediction
        ensemble_diagnostics: Dict[str, Any] = {
            "status": "ok",
            "components": list(MODEL_NAMES),
            "weights": {
                name: round(1.0 / len(MODEL_NAMES), 6)
                for name in MODEL_NAMES
            },
            "train_samples": int(X_train.shape[0]),
            "train_features": int(X_train.shape[1]),
        }
    else:
        predictions[ENSEMBLE_NAME] = None
        failed_components = [
            name for name in MODEL_NAMES if model_predictions[name] is None
        ]
        ensemble_diagnostics = {
            "status": "unavailable",
            "error": "One or more component models failed: "
            + ", ".join(failed_components),
            "components": list(MODEL_NAMES),
            "train_samples": int(X_train.shape[0]),
            "train_features": int(X_train.shape[1]),
        }

    model_reports: Dict[str, Dict[str, Any]] = {}
    for name in MODEL_NAMES:
        report = dict(model_diagnostics[name])
        prediction = predictions[name]
        report["metrics"] = (
            calculate_metrics(y_validation, prediction, current_close)
            if prediction is not None
            else None
        )
        model_reports[name] = report

    model_reports[BASELINE_NAME] = {
        "status": "ok",
        "train_samples": 0,
        "train_features": int(X_train.shape[1]),
        "preprocessing": None,
        "metrics": calculate_metrics(
            y_validation, baseline_prediction, current_close
        ),
    }
    model_reports[ENSEMBLE_NAME] = {
        **ensemble_diagnostics,
        "metrics": (
            calculate_metrics(
                y_validation,
                predictions[ENSEMBLE_NAME],
                current_close,
            )
            if predictions[ENSEMBLE_NAME] is not None
            else None
        ),
    }

    baseline_metrics = model_reports[BASELINE_NAME]["metrics"]
    baseline_comparison = {
        name: compare_metrics_to_baseline(report["metrics"], baseline_metrics)
        for name, report in model_reports.items()
        if name != BASELINE_NAME and report["metrics"] is not None
    }

    successful_predictions = {
        name: prediction
        for name, prediction in predictions.items()
        if prediction is not None
    }
    validation_metadata = _validation_metadata(
        validation, successful_predictions
    )

    errors = [
        {
            "model": name,
            "status": report.get("status"),
            "error": report.get("error"),
        }
        for name, report in model_reports.items()
        if report.get("status") not in {"ok"}
    ]

    all_required_ok = all(
        model_reports[name]["status"] == "ok"
        for name in MODEL_NAMES + (ENSEMBLE_NAME,)
    )
    any_ok = any(
        report["metrics"] is not None for report in model_reports.values()
    )
    status = "ok" if all_required_ok else ("partial" if any_ok else "failed")

    return {
        "label": label,
        "status": status,
        "errors": errors,
        "train": {
            "samples": int(len(train)),
            "start": _iso_date(train["Date"].iloc[0]),
            "end": _iso_date(train["Date"].iloc[-1]),
            "target_start": _iso_date(train["Target_Date"].iloc[0]),
            "target_end": _iso_date(train["Target_Date"].iloc[-1]),
        },
        "validation": validation_metadata,
        "models": model_reports,
        "baseline_comparison": baseline_comparison,
    }


def _rank_metrics(
    metrics_by_name: Mapping[str, Optional[Dict[str, Any]]],
    selection_metric: str,
) -> List[Dict[str, Any]]:
    """Rank candidates without using R² as the primary criterion."""

    primary = selection_metric if selection_metric in {"mae", "rmse"} else "rmse"
    secondary = "mae" if primary == "rmse" else "rmse"

    def sort_key(name: str):
        metrics = metrics_by_name[name] or {}
        primary_value = metrics.get(primary)
        secondary_value = metrics.get(secondary)
        directional = metrics.get("directional_accuracy")
        return (
            primary_value if primary_value is not None else float("inf"),
            secondary_value if secondary_value is not None else float("inf"),
            -directional if directional is not None else float("inf"),
            name,
        )

    ranked_names = sorted(
        (
            name
            for name, metrics in metrics_by_name.items()
            if metrics is not None
        ),
        key=sort_key,
    )
    return [
        {
            "rank": rank,
            "model": name,
            "label": MODEL_LABELS.get(name, name),
            "metrics": metrics_by_name[name],
        }
        for rank, name in enumerate(ranked_names, start=1)
    ]


class WalkForwardEvaluationService:
    """Orchestrates chronological walk-forward evaluation and reporting."""

    def __init__(
        self,
        config: Optional[EvaluationConfig] = None,
        data_service_override: Any = None,
        feature_engineering_override: Any = None,
        model_factories: Optional[Mapping[str, Callable[[], Any]]] = None,
        report_dir: Optional[str] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.config = config or EvaluationConfig.from_settings()
        self.data_service = data_service_override or data_service
        self.feature_engineering = (
            feature_engineering_override or feature_engineering
        )
        factories = dict(model_factories or MODEL_FACTORIES)
        missing = [name for name in MODEL_NAMES if name not in factories]
        if missing:
            raise ValueError(
                "Missing model factories for: " + ", ".join(missing)
            )
        self.model_factories = factories
        self.report_dir = report_dir or settings.EVALUATION_REPORT_DIR
        self.now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    def evaluate_symbol(
        self,
        symbol: str,
        config: Optional[EvaluationConfig] = None,
        write_report: bool = True,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Evaluate one symbol and optionally write a JSON report."""

        active_config = config or self.config
        active_config.validate()
        normalized_symbol = validate_symbol(symbol)

        raw_data = self.data_service.fetch_stock_data(
            normalized_symbol, active_config.period
        )
        clean_data = self.data_service.clean_data(raw_data)
        dataset = build_evaluation_dataset(
            clean_data,
            feature_engineering_service=self.feature_engineering,
        )
        development, holdout, holdout_info = split_development_holdout(
            dataset, active_config
        )
        folds, fold_metadata = generate_walk_forward_folds(
            development, active_config
        )

        fold_reports: List[Dict[str, Any]] = []
        pooled_actual: Dict[str, List[np.ndarray]] = {
            name: [] for name in ALL_CANDIDATE_NAMES
        }
        pooled_predictions: Dict[str, List[np.ndarray]] = {
            name: [] for name in ALL_CANDIDATE_NAMES
        }
        pooled_current: Dict[str, List[np.ndarray]] = {
            name: [] for name in ALL_CANDIDATE_NAMES
        }
        successful_folds: Dict[str, List[int]] = {
            name: [] for name in ALL_CANDIDATE_NAMES
        }

        for fold in folds:
            train = development.iloc[fold.train_indices]
            validation = development.iloc[fold.validation_indices]
            fold_report = _evaluate_rows(
                model_factories=self.model_factories,
                train=train,
                validation=validation,
                feature_columns=dataset.feature_columns,
                label=f"fold_{fold.fold}",
            )
            fold_report["fold"] = fold.fold
            fold_report["train"] = _fold_train_metadata(
                development, fold.train_indices
            )
            fold_report["validation"]["start"] = _iso_date(
                fold.validation_start
            )
            fold_report["validation"]["end"] = _iso_date(fold.validation_end)
            fold_report["validation"]["target_start"] = _iso_date(
                fold.validation_target_start
            )
            fold_report["validation"]["target_end"] = _iso_date(
                fold.validation_target_end
            )
            fold_report["train"]["target_start"] = _iso_date(
                fold.train_target_start
            )
            fold_report["train"]["target_end"] = _iso_date(
                fold.train_target_end
            )
            fold_reports.append(fold_report)

            actual = validation["Next_Day_Close"].to_numpy(dtype=float)
            current = validation["Close"].to_numpy(dtype=float)
            for name in ALL_CANDIDATE_NAMES:
                prediction = fold_report["validation"]["predictions"].get(name)
                if prediction is not None:
                    pooled_actual[name].append(actual)
                    pooled_current[name].append(current)
                    pooled_predictions[name].append(
                        np.asarray(prediction, dtype=float)
                    )
                    successful_folds[name].append(fold.fold)

        aggregated: Dict[str, Dict[str, Any]] = {}
        aggregate_metrics: Dict[str, Optional[Dict[str, Any]]] = {}
        for name in ALL_CANDIDATE_NAMES:
            if len(successful_folds[name]) == len(fold_reports):
                metrics = calculate_metrics(
                    np.concatenate(pooled_actual[name]),
                    np.concatenate(pooled_predictions[name]),
                    np.concatenate(pooled_current[name]),
                )
                aggregate_metrics[name] = metrics
                aggregated[name] = {
                    "status": "comparable",
                    "folds_evaluated": len(fold_reports),
                    "missing_folds": [],
                    "metrics": metrics,
                    "validation_samples": metrics["n_samples"],
                    "label": MODEL_LABELS.get(name, name),
                }
            else:
                missing_folds = [
                    fold_report["fold"]
                    for fold_report in fold_reports
                    if name
                    not in fold_report["validation"]["predictions"]
                ]
                aggregate_metrics[name] = None
                aggregated[name] = {
                    "status": "incomplete",
                    "folds_evaluated": len(successful_folds[name]),
                    "missing_folds": missing_folds,
                    "metrics": None,
                    "validation_samples": int(
                        sum(
                            len(values)
                            for values in pooled_actual[name]
                        )
                    ),
                    "label": MODEL_LABELS.get(name, name),
                }

        baseline_dev_metrics = aggregate_metrics[BASELINE_NAME]
        development_baseline_comparison = {
            name: compare_metrics_to_baseline(
                aggregate_metrics[name], baseline_dev_metrics
            )
            for name in ALL_CANDIDATE_NAMES
            if name != BASELINE_NAME
            and aggregate_metrics[name] is not None
        }

        ranking_all = _rank_metrics(
            aggregate_metrics, active_config.selection_metric
        )
        deployable_metrics = {
            name: aggregate_metrics[name]
            for name in MODEL_NAMES + (ENSEMBLE_NAME,)
        }
        ranking_deployable = _rank_metrics(
            deployable_metrics, active_config.selection_metric
        )
        selected_model = (
            ranking_deployable[0]["model"]
            if ranking_deployable
            else None
        )
        best_overall = ranking_all[0]["model"] if ranking_all else None
        selected_development_metrics = (
            aggregate_metrics.get(selected_model)
            if selected_model is not None
            else None
        )

        selection_info = {
            "selected_model": selected_model,
            "selected_model_label": (
                MODEL_LABELS.get(selected_model)
                if selected_model is not None
                else None
            ),
            "selection_metric": active_config.selection_metric,
            "tie_break_order": [
                active_config.selection_metric,
                "mae" if active_config.selection_metric == "rmse" else "rmse",
                "directional_accuracy",
            ],
            "ranking_development_all_candidates": ranking_all,
            "ranking_development_ml_and_ensemble": ranking_deployable,
            "best_overall_including_baseline": best_overall,
            "selected_model_development_metrics": selected_development_metrics,
            "holdout_used_for_selection": False,
            "selection_locked_before_holdout": True,
            "note": (
                "Model selection uses only pooled development walk-forward "
                "validation metrics. The final holdout is evaluated after "
                "this selection is recorded."
            ),
        }

        # ------------------------------------------------------------------
        # Final holdout: selection has already been locked above.  Refit all
        # candidates on development data, then evaluate the untouched holdout.
        # ------------------------------------------------------------------
        holdout_target_start = holdout["Target_Date"].iloc[0]
        holdout_train_end = int(
            np.count_nonzero(
                (development["Target_Date"] < holdout_target_start).to_numpy()
            )
        )
        if holdout_train_end < active_config.min_train_samples:
            raise InsufficientEvaluationData(
                "Not enough development rows before the final holdout: "
                f"{holdout_train_end} < {active_config.min_train_samples}"
            )
        holdout_train = development.iloc[:holdout_train_end]
        if not (
            holdout_train["Target_Date"].iloc[-1] < holdout_target_start
        ):
            raise ValueError("Final holdout training targets overlap holdout targets")
        if not (
            holdout_train["Date"].iloc[-1] < holdout["Date"].iloc[0]
        ):
            raise ValueError("Final holdout training features overlap holdout features")

        holdout_report = _evaluate_rows(
            model_factories=self.model_factories,
            train=holdout_train,
            validation=holdout,
            feature_columns=dataset.feature_columns,
            label="final_holdout",
        )
        holdout_report["holdout_index_start"] = int(
            holdout_info["holdout_start_index"]
        )
        holdout_report["holdout_index_end"] = int(
            holdout_info["holdout_end_index"]
        )
        holdout_metrics = {
            name: holdout_report["models"][name]["metrics"]
            for name in ALL_CANDIDATE_NAMES
        }
        baseline_holdout_metrics = holdout_metrics[BASELINE_NAME]
        holdout_baseline_comparison = {
            name: compare_metrics_to_baseline(
                holdout_metrics[name], baseline_holdout_metrics
            )
            for name in ALL_CANDIDATE_NAMES
            if name != BASELINE_NAME and holdout_metrics[name] is not None
        }
        holdout_ranking = _rank_metrics(
            holdout_metrics, active_config.selection_metric
        )
        holdout_best = (
            holdout_ranking[0]["model"] if holdout_ranking else None
        )
        holdout_report["baseline_comparison"] = holdout_baseline_comparison
        holdout_report["best_model_by_holdout_metrics"] = holdout_best
        holdout_report["selected_model_metrics"] = (
            holdout_metrics.get(selected_model)
            if selected_model is not None
            else None
        )

        ensemble_dev_metrics = aggregate_metrics[ENSEMBLE_NAME]
        ensemble_holdout_metrics = holdout_metrics[ENSEMBLE_NAME]
        ensemble_beats_baseline_development = bool(
            ensemble_dev_metrics is not None
            and baseline_dev_metrics is not None
            and ensemble_dev_metrics["rmse"] is not None
            and baseline_dev_metrics["rmse"] is not None
            and ensemble_dev_metrics["rmse"] < baseline_dev_metrics["rmse"]
        )
        ensemble_beats_baseline_holdout = bool(
            ensemble_holdout_metrics is not None
            and baseline_holdout_metrics is not None
            and ensemble_holdout_metrics["rmse"] is not None
            and baseline_holdout_metrics["rmse"] is not None
            and ensemble_holdout_metrics["rmse"] < baseline_holdout_metrics["rmse"]
        )

        models_beating_baseline_development = [
            name
            for name in MODEL_NAMES + (ENSEMBLE_NAME,)
            if development_baseline_comparison.get(name, {}).get(
                "beats_baseline_on_rmse", False
            )
        ]
        models_beating_baseline_holdout = [
            name
            for name in MODEL_NAMES + (ENSEMBLE_NAME,)
            if holdout_baseline_comparison.get(name, {}).get(
                "beats_baseline_on_rmse", False
            )
        ]

        warnings: List[str] = []
        if fold_metadata["folds_reduced"]:
            warnings.append(
                f"Requested {fold_metadata['requested_folds']} folds but used "
                f"{fold_metadata['folds_used']} because of available history."
            )
        if holdout_info["holdout_size_adjusted"]:
            warnings.append(
                "The final holdout was reduced from the requested size to "
                "preserve the minimum development data for walk-forward folds."
            )
        if selected_model is None:
            warnings.append(
                "No ML/ensemble candidate had complete comparable development "
                "metrics; no deployable model was selected."
            )
        elif not development_baseline_comparison.get(
            selected_model, {}
        ).get("beats_baseline_on_rmse", False):
            warnings.append(
                "The selected ML/ensemble candidate did not beat the naive "
                "persistence baseline on development RMSE."
            )
        if any(fold_report["status"] != "ok" for fold_report in fold_reports):
            warnings.append(
                "One or more development folds had model failures; failures "
                "are recorded in the report and excluded from comparable "
                "aggregates only where necessary."
            )
        if holdout_report["status"] != "ok":
            warnings.append(
                "One or more final-holdout model fits failed; see "
                "final_holdout.errors and per-model statuses."
            )
        if ensemble_dev_metrics is None or ensemble_holdout_metrics is None:
            warnings.append(
                "The equal-weight ensemble was unavailable for at least one "
                "period because a component model failed."
            )

        methodology = {
            "validation_method": "expanding-window walk-forward validation",
            "target": "Next_Day_Close (one trading session ahead)",
            "baseline": (
                "naive persistence: predicted next-day close equals the "
                "current-day close"
            ),
            "shuffle": False,
            "feature_calculation": (
                "causal rolling/EWM indicators using only the current row and "
                "earlier rows; features are not fitted to a global dataset"
            ),
            "preprocessing": (
                "SVR StandardScaler is fitted separately on each fold's "
                "training rows and is never fitted or reused on validation "
                "rows or other folds"
            ),
            "training_window": (
                "expanding; each fold uses a contiguous chronological prefix "
                "whose target dates precede the validation target period"
            ),
            "fold_selection": (
                "contiguous chronological validation blocks; no shuffle and "
                "no overlap"
            ),
            "holdout": (
                "most recent chronological target rows reserved before model "
                "selection; not used for tuning, selection, or ensemble weights"
            ),
            "ensemble": (
                "existing equal-weight mean of the five model predictions; "
                "production ensemble behavior was not changed"
            ),
            "selection": (
                "development pooled walk-forward RMSE first, then MAE, then "
                "higher directional accuracy among non-abstaining signals; "
                "R² is reported but is not the primary ranking criterion"
            ),
        }

        metric_definitions = {
            "mae": "Mean absolute error in price units.",
            "mse": "Mean squared error in squared price units.",
            "rmse": "Root mean squared error in price units.",
            "r2_score": (
                "Coefficient of determination; null when fewer than two rows "
                "or the actual target series is constant."
            ),
            "smape": (
                "Symmetric mean absolute percentage error (%); zero/zero "
                "pairs contribute zero and one-zero pairs contribute 200%."
            ),
            "mape": (
                "Mean absolute percentage error (%); rows with zero actual "
                "values are excluded. Retained as a supplementary metric."
            ),
            "nmae_pct": (
                "MAE divided by the mean absolute current price level (%), "
                "making errors comparable across stocks with different prices."
            ),
            "nrmse_pct": (
                "RMSE divided by the mean absolute current price level (%)."
            ),
            "mase_vs_random_walk": (
                "MAE divided by the mean absolute one-step actual price change. "
                "Values below 1 beat the random-walk change benchmark on MAE."
            ),
            "signal_coverage": (
                "Percentage of directional-eligible predictions with a "
                "non-zero predicted movement. Zero predictions are abstentions."
            ),
            "signal_coverage_of_moving_days": (
                "Percentage of actual moving days on which the model produced "
                "a non-zero directional signal."
            ),
            "abstention_rate": (
                "Percentage of directional-eligible predictions with exactly "
                "zero predicted movement."
            ),
            "directional_accuracy": (
                "Percentage of correct directions among non-zero predictions "
                "on actual moving days. Zero predicted movement is an "
                "abstention, so an abstaining model has null directional "
                "accuracy rather than an artificial zero."
            ),
        }

        limitations = [
            "Evaluation uses daily OHLCV data from yfinance; vendor revisions, "
            "missing sessions, and a current or partially formed daily bar can "
            "change historical values and rerun results.",
            "Walk-forward validation reduces look-ahead bias but cannot "
            "eliminate regime changes, survivorship concerns, or model risk.",
            "Hyperparameters are the existing fixed values and were not tuned "
            "on validation or holdout data.",
            "Metrics are one-step-ahead close-price errors; transaction costs, "
            "slippage, liquidity, and intraday execution are not modeled.",
            "The final holdout is one chronological period and may not "
            "represent future market conditions.",
            "A persistence baseline is a strong benchmark for near-random-walk "
            "price series; lower ML error is not guaranteed.",
        ]
        limitations.extend(warnings)

        report: Dict[str, Any] = {
            "schema_version": "1.0",
            "symbol": normalized_symbol,
            "generated_at": self.now_provider().astimezone(timezone.utc).isoformat(),
            "status": "completed",
            "config": active_config.to_dict(),
            "methodology": methodology,
            "metric_definitions": metric_definitions,
            "data": {
                "source": "yfinance",
                "period": active_config.period,
                "raw_rows": int(len(raw_data)),
                "clean_rows": int(len(clean_data)),
                "feature_rows": int(len(dataset.featured_df)),
                "feature_period": {
                    "start": _iso_date(dataset.featured_df["Date"].iloc[0]),
                    "end": _iso_date(dataset.featured_df["Date"].iloc[-1]),
                },
                "target_period": {
                    "start": _iso_date(
                        dataset.featured_df["Target_Date"].iloc[0]
                    ),
                    "end": _iso_date(
                        dataset.featured_df["Target_Date"].iloc[-1]
                    ),
                },
                "feature_columns": list(dataset.feature_columns),
                "data_fingerprint_sha256": dataset.data_fingerprint,
                "holdout_split": holdout_info,
            },
            "sample_counts": {
                "folds": len(folds),
                "development_rows": int(len(development)),
                "development_validation_samples": int(
                    sum(len(fold.validation_indices) for fold in folds)
                ),
                "holdout_training_samples": int(len(holdout_train)),
                "holdout_validation_samples": int(len(holdout)),
            },
            "development_validation": {
                "fold_generation": fold_metadata,
                "folds": fold_reports,
                "aggregated": aggregated,
                "baseline_comparison": development_baseline_comparison,
                "model_selection": selection_info,
            },
            "final_holdout": {
                **holdout_report,
                "selection_locked_before_holdout": True,
                "baseline_comparison": holdout_baseline_comparison,
            },
            "best_performing_model": {
                "selected_model": selected_model,
                "selected_model_label": (
                    MODEL_LABELS.get(selected_model)
                    if selected_model is not None
                    else None
                ),
                "selected_on": (
                    "pooled development walk-forward metrics; holdout not used"
                ),
                "selection_metric": active_config.selection_metric,
                "development_metrics": selected_development_metrics,
                "final_holdout_metrics": (
                    holdout_metrics.get(selected_model)
                    if selected_model is not None
                    else None
                ),
                "best_overall_including_baseline": best_overall,
                "best_holdout_model_by_rmse_order": holdout_best,
                "best_holdout_model_note": (
                    "Reported for information only after model selection was "
                    "locked; holdout metrics were not used for selection."
                ),
            },
            "baseline_comparison": {
                "baseline_name": BASELINE_NAME,
                "baseline_label": MODEL_LABELS[BASELINE_NAME],
                "development": development_baseline_comparison,
                "final_holdout": holdout_baseline_comparison,
                "models_beating_baseline_on_development_rmse": (
                    models_beating_baseline_development
                ),
                "models_beating_baseline_on_final_holdout_rmse": (
                    models_beating_baseline_holdout
                ),
            },
            "ensemble_evaluation": {
                "name": ENSEMBLE_NAME,
                "label": MODEL_LABELS[ENSEMBLE_NAME],
                "equal_weight": True,
                "weights": {
                    name: round(1.0 / len(MODEL_NAMES), 6)
                    for name in MODEL_NAMES
                },
                "development_metrics": ensemble_dev_metrics,
                "final_holdout_metrics": ensemble_holdout_metrics,
                "baseline_development_metrics": baseline_dev_metrics,
                "baseline_final_holdout_metrics": baseline_holdout_metrics,
                "beats_baseline_development_rmse": (
                    ensemble_beats_baseline_development
                ),
                "beats_baseline_final_holdout_rmse": (
                    ensemble_beats_baseline_holdout
                ),
                "production_ensemble_behavior_changed": False,
            },
            "warnings": warnings,
            "limitations": limitations,
        }

        safe_report = _json_safe(report)
        if write_report:
            report_path = self.save_report(safe_report, output_dir=output_dir)
            safe_report["report_path"] = report_path
        return safe_report

    def save_report(
        self,
        report: Mapping[str, Any],
        output_dir: Optional[str] = None,
    ) -> str:
        """Write a deterministic JSON report and return its path."""

        directory = output_dir or self.report_dir
        os.makedirs(directory, exist_ok=True)
        symbol = str(report.get("symbol", "symbol"))
        file_name = symbol.replace(".", "_") + "_walk_forward.json"
        path = os.path.join(directory, file_name)
        serialized = json.dumps(
            _json_safe(dict(report)),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized + "\n")
        return path


walk_forward_evaluation_service = WalkForwardEvaluationService()
