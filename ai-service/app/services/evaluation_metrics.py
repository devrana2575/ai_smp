"""Safe metrics for chronological model evaluation.

All functions in this module are intentionally independent of any model or
data source. They are used by the walk-forward, return-forecasting, and
backtesting research services and can also be tested directly with synthetic
arrays.

Directional semantics
---------------------
A predicted movement of exactly zero is an **abstention**, not a wrong
direction. Directional accuracy is therefore calculated only on non-zero
predictions whose actual price also moved. Signal coverage reports how often a
model produced a directional signal, and the abstention rate reports how often
it declined to do so. A persistence forecast predicts zero return by
construction, so it receives an abstention/coverage of zero rather than an
artificially assigned directional accuracy of zero.

Percentage metrics are returned as percentages (for example, 12.5 means
12.5%), not as fractions.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np


def _as_float_array(values: Any, name: str) -> np.ndarray:
    array = np.asarray(values, dtype=float).reshape(-1)
    if array.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    return array


def _round_or_none(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    value = float(value)
    if not np.isfinite(value):
        return None
    return round(value, digits)


def _safe_ratio(
    numerator: Optional[float],
    denominator: Optional[float],
    multiplier: float = 1.0,
) -> Optional[float]:
    if numerator is None or denominator is None:
        return None
    denominator = float(denominator)
    if denominator == 0.0 or not np.isfinite(denominator):
        return None
    return _round_or_none(float(numerator) / denominator * multiplier)


def _directional_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
    current: Optional[np.ndarray],
) -> Dict[str, Any]:
    """Calculate abstention-aware directional statistics.

    ``current`` is the price against which both actual and predicted movement
    are measured. For return forecasts, callers pass zeros so the return itself
    is the movement.
    """

    empty = {
        "directional_samples": 0,
        "signal_samples": 0,
        "directional_signal_samples": 0,
        "directional_correct": 0,
        "signal_coverage": None,
        "signal_coverage_of_moving_days": None,
        "abstention_rate": None,
        "directional_accuracy": None,
    }
    if current is None:
        return empty

    finite = np.isfinite(actual) & np.isfinite(predicted) & np.isfinite(current)
    if not np.any(finite):
        return empty

    actual_movement = actual[finite] - current[finite]
    predicted_movement = predicted[finite] - current[finite]
    actual_direction = np.sign(actual_movement)
    predicted_direction = np.sign(predicted_movement)

    moved = actual_direction != 0.0
    signaled = predicted_direction != 0.0
    directional_eligible = int(np.count_nonzero(finite))
    directional_samples = int(np.count_nonzero(moved))
    signal_samples = int(np.count_nonzero(signaled))
    directional_signal_samples = int(np.count_nonzero(signaled & moved))
    abstentions = int(np.count_nonzero(~signaled))

    correct = int(
        np.count_nonzero(
            signaled & moved & (predicted_direction == actual_direction)
        )
    )

    directional_accuracy: Optional[float] = None
    if directional_signal_samples > 0:
        directional_accuracy = (
            correct / directional_signal_samples * 100.0
        )

    return {
        "directional_samples": directional_samples,
        "signal_samples": signal_samples,
        "directional_signal_samples": directional_signal_samples,
        "directional_correct": correct,
        "signal_coverage": _safe_ratio(
            signal_samples, directional_eligible, 100.0
        ),
        "signal_coverage_of_moving_days": _safe_ratio(
            directional_signal_samples, directional_samples, 100.0
        ),
        "abstention_rate": _safe_ratio(
            abstentions, directional_eligible, 100.0
        ),
        "directional_accuracy": _round_or_none(directional_accuracy),
    }


def calculate_metrics(
    y_true: Any,
    y_pred: Any,
    current_prices: Any = None,
) -> Dict[str, Any]:
    """Calculate price metrics safely and with abstention-aware direction.

    Parameters
    ----------
    y_true:
        Actual next-period values.
    y_pred:
        Predicted next-period values.
    current_prices:
        Optional current-period prices used to determine price movements for
        directional accuracy. When omitted, directional accuracy is ``None``.

    Rows containing non-finite target or prediction values are excluded. If
    there are no usable rows, numeric metrics are returned as ``None`` rather
    than NaN. R² is also ``None`` when it is mathematically undefined (fewer
    than two observations or a constant target series).
    """

    true = _as_float_array(y_true, "y_true")
    pred = _as_float_array(y_pred, "y_pred")

    if true.shape != pred.shape:
        raise ValueError(
            "y_true and y_pred must have the same shape; "
            f"got {true.shape} and {pred.shape}"
        )

    current: Optional[np.ndarray] = None
    if current_prices is not None:
        current = _as_float_array(current_prices, "current_prices")
        if current.shape != true.shape:
            raise ValueError(
                "current_prices must have the same shape as y_true/y_pred; "
                f"got {current.shape} and {true.shape}"
            )

    finite_mask = np.isfinite(true) & np.isfinite(pred)
    true = true[finite_mask]
    pred = pred[finite_mask]
    if current is not None:
        current = current[finite_mask]

    n_samples = int(true.size)
    if n_samples == 0:
        return {
            "n_samples": 0,
            "directional_samples": 0,
            "signal_samples": 0,
            "directional_signal_samples": 0,
            "directional_correct": 0,
            "signal_coverage": None,
            "signal_coverage_of_moving_days": None,
            "abstention_rate": None,
            "mae": None,
            "mse": None,
            "rmse": None,
            "r2_score": None,
            "smape": None,
            "mape": None,
            "directional_accuracy": None,
            "mean_current_price": None,
            "mean_actual_price": None,
            "mean_abs_actual_change": None,
            "nmae_pct": None,
            "nrmse_pct": None,
            "mase_vs_random_walk": None,
        }

    errors = true - pred
    absolute_errors = np.abs(errors)
    squared_errors = np.square(errors)

    mae = float(np.mean(absolute_errors))
    mse = float(np.mean(squared_errors))
    rmse = float(np.sqrt(mse))

    ss_res = float(np.sum(squared_errors))
    centered = true - float(np.mean(true))
    ss_tot = float(np.sum(np.square(centered)))
    if n_samples < 2 or ss_tot == 0.0:
        r2: Optional[float] = None
    else:
        r2 = 1.0 - (ss_res / ss_tot)

    smape_denominator = np.abs(true) + np.abs(pred)
    smape_terms = np.zeros_like(smape_denominator, dtype=float)
    nonzero_denominator = smape_denominator != 0.0
    smape_terms[nonzero_denominator] = (
        2.0
        * np.abs(errors[nonzero_denominator])
        / smape_denominator[nonzero_denominator]
    )
    smape = float(np.mean(smape_terms) * 100.0)

    # MAPE is retained as a supplementary compatibility metric. Rows whose
    # actual value is zero are excluded because percentage error is undefined.
    nonzero_true = true != 0.0
    if np.any(nonzero_true):
        mape = float(
            np.mean(np.abs(errors[nonzero_true] / true[nonzero_true])) * 100.0
        )
    else:
        mape = None

    direction = _directional_metrics(true, pred, current)

    # Normalized error metrics make errors comparable across stocks with
    # different price levels. The reference is the mean absolute price level;
    # MASE is relative to the naive random-walk change.
    reference_values = current if current is not None else true
    finite_reference = reference_values[np.isfinite(reference_values)]
    mean_current = (
        float(np.mean(np.abs(finite_reference)))
        if finite_reference.size
        else None
    )
    mean_actual = float(np.mean(np.abs(true)))
    mean_abs_change: Optional[float] = None
    if current is not None:
        change = np.abs(true - current)
        change = change[np.isfinite(change)]
        if change.size:
            mean_abs_change = float(np.mean(change))

    nmae = _safe_ratio(mae, mean_current, 100.0)
    nrmse = _safe_ratio(rmse, mean_current, 100.0)
    mase = _safe_ratio(mae, mean_abs_change)

    return {
        "n_samples": n_samples,
        **direction,
        "mae": _round_or_none(mae),
        "mse": _round_or_none(mse),
        "rmse": _round_or_none(rmse),
        "r2_score": _round_or_none(r2),
        "smape": _round_or_none(smape),
        "mape": _round_or_none(mape),
        "mean_current_price": _round_or_none(mean_current),
        "mean_actual_price": _round_or_none(mean_actual),
        "mean_abs_actual_change": _round_or_none(mean_abs_change),
        "nmae_pct": nmae,
        "nrmse_pct": nrmse,
        "mase_vs_random_walk": mase,
    }


def calculate_return_metrics(
    y_true: Any,
    y_pred: Any,
) -> Dict[str, Any]:
    """Calculate return-forecast metrics with abstention-aware direction.

    The zero-return baseline is represented by a zero prediction. It therefore
    has zero signal coverage and an undefined directional accuracy, not a
    directional score of zero.
    """

    true = _as_float_array(y_true, "y_true")
    pred = _as_float_array(y_pred, "y_pred")
    if true.shape != pred.shape:
        raise ValueError(
            "y_true and y_pred must have the same shape; "
            f"got {true.shape} and {pred.shape}"
        )

    base = calculate_metrics(true, pred, np.zeros_like(true))
    mean_abs_return: Optional[float] = None
    finite = np.isfinite(true) & np.isfinite(pred)
    if np.any(finite):
        mean_abs_return = float(np.mean(np.abs(true[finite])))

    relative_mae = _safe_ratio(base.get("mae"), mean_abs_return)
    relative_rmse = _safe_ratio(base.get("rmse"), mean_abs_return)

    return {
        **base,
        "return_mae": base.get("mae"),
        "return_rmse": base.get("rmse"),
        "mean_abs_actual_return": _round_or_none(mean_abs_return),
        "relative_return_mae": relative_mae,
        "relative_return_rmse": relative_rmse,
    }


def _improvement_percentage(
    candidate_value: Optional[float],
    baseline_value: Optional[float],
) -> Optional[float]:
    if candidate_value is None or baseline_value is None or baseline_value == 0:
        return None
    return _round_or_none(
        (float(baseline_value) - float(candidate_value))
        / abs(float(baseline_value))
        * 100.0
    )


def compare_metrics_to_baseline(
    candidate_metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare a candidate's metrics with the naive baseline metrics.

    The primary ``beats_baseline`` flag uses RMSE, matching the default model
    selection metric. Component flags for MAE, sMAPE, and directional accuracy
    are included so a single metric cannot hide mixed results.

    Directional comparisons are only marked as beats/losses when both
    candidates actually produced directional signals. An abstaining baseline
    does not receive an artificial zero accuracy and does not create a
    misleading directional win.
    """

    candidate_mae = candidate_metrics.get("mae")
    baseline_mae = baseline_metrics.get("mae")
    candidate_rmse = candidate_metrics.get("rmse")
    baseline_rmse = baseline_metrics.get("rmse")
    candidate_smape = candidate_metrics.get("smape")
    baseline_smape = baseline_metrics.get("smape")
    candidate_directional = candidate_metrics.get("directional_accuracy")
    baseline_directional = baseline_metrics.get("directional_accuracy")
    candidate_coverage = candidate_metrics.get("signal_coverage")
    baseline_coverage = baseline_metrics.get("signal_coverage")

    beats_rmse = (
        candidate_rmse is not None
        and baseline_rmse is not None
        and candidate_rmse < baseline_rmse
    )
    beats_mae = (
        candidate_mae is not None
        and baseline_mae is not None
        and candidate_mae < baseline_mae
    )
    beats_smape = (
        candidate_smape is not None
        and baseline_smape is not None
        and candidate_smape < baseline_smape
    )
    directional_comparable = (
        candidate_directional is not None and baseline_directional is not None
    )
    beats_directional = bool(
        directional_comparable
        and candidate_directional > baseline_directional
    )
    loses_directional = bool(
        directional_comparable
        and candidate_directional < baseline_directional
    )

    directional_delta: Optional[float] = None
    if directional_comparable:
        directional_delta = _round_or_none(
            float(candidate_directional) - float(baseline_directional)
        )

    coverage_delta: Optional[float] = None
    if candidate_coverage is not None and baseline_coverage is not None:
        coverage_delta = _round_or_none(
            float(candidate_coverage) - float(baseline_coverage)
        )

    return {
        "beats_baseline": bool(beats_rmse),
        "beats_baseline_on_rmse": bool(beats_rmse),
        "beats_baseline_on_mae": bool(beats_mae),
        "beats_baseline_on_smape": bool(beats_smape),
        "directional_accuracy_comparable": bool(directional_comparable),
        "beats_baseline_on_directional_accuracy": bool(beats_directional),
        "loses_to_baseline_on_directional_accuracy": bool(loses_directional),
        "mae_improvement_pct": _improvement_percentage(
            candidate_mae, baseline_mae
        ),
        "rmse_improvement_pct": _improvement_percentage(
            candidate_rmse, baseline_rmse
        ),
        "smape_improvement_pct": _improvement_percentage(
            candidate_smape, baseline_smape
        ),
        "directional_accuracy_delta_pp": directional_delta,
        "signal_coverage_delta_pp": coverage_delta,
        "candidate_signal_coverage": candidate_coverage,
        "baseline_signal_coverage": baseline_coverage,
        "note": (
            "Directional accuracy is compared only when both candidates "
            "produced non-zero directional signals; an abstaining baseline "
            "is not assigned an artificial zero directional score."
        ),
    }
