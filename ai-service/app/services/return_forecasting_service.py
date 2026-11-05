"""Independent return-based forecasting experiment.

This service deliberately does not touch production inference or saved model
artifacts. It trains the existing five algorithms on three target formulations
using the same chronological folds and final-holdout boundaries as the Phase 2
walk-forward evaluation:

* absolute next-day close price,
* simple next-day return, and
* log next-day return.

All return predictions are reconstructed into prices for price-level metrics.
A zero-return persistence baseline is evaluated in every family. Zero-return
predictions are abstentions for directional metrics, not artificial directional
errors.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from app.config import settings
from app.services.data_service import data_service, validate_symbol
from app.services.evaluation_metrics import (
    calculate_metrics,
    calculate_return_metrics,
    compare_metrics_to_baseline,
)
from app.services.feature_engineering import feature_engineering
from app.services.walk_forward_evaluation import (
    ENSEMBLE_NAME,
    MODEL_FACTORIES,
    MODEL_LABELS,
    MODEL_NAMES,
    EvaluationConfig,
    EvaluationDataset,
    _fit_models_for_fold,
    _iso_date,
    _json_safe,
    build_evaluation_dataset,
    generate_walk_forward_folds,
    split_development_holdout,
)


ZERO_RETURN_NAME = "zero_return_persistence"
FAMILY_ABSOLUTE = "absolute_price"
FAMILY_SIMPLE = "simple_return"
FAMILY_LOG = "log_return"
FAMILIES: Tuple[str, ...] = (FAMILY_ABSOLUTE, FAMILY_SIMPLE, FAMILY_LOG)
CANDIDATE_NAMES: Tuple[str, ...] = MODEL_NAMES + (
    ZERO_RETURN_NAME,
    ENSEMBLE_NAME,
)
LABELS = {
    **MODEL_LABELS,
    ZERO_RETURN_NAME: "Zero-Return Persistence",
}


class ReturnForecastingService:
    """Run the return-forecasting experiment for one symbol."""

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
        self.report_dir = report_dir or settings.RETURN_REPORT_DIR
        self.now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    # ------------------------------------------------------------------
    # Data preparation
    # ------------------------------------------------------------------
    def prepare_symbol(
        self,
        symbol: str,
        config: Optional[EvaluationConfig] = None,
    ) -> Dict[str, Any]:
        active = config or self.config
        active.validate()
        normalized = validate_symbol(symbol)

        raw_data = self.data_service.fetch_stock_data(
            normalized, active.period
        )
        clean_data = self.data_service.clean_data(raw_data)
        dataset = build_evaluation_dataset(
            clean_data,
            feature_engineering_service=self.feature_engineering,
        )

        featured = dataset.featured_df.copy()
        ratio = featured["Next_Day_Close"] / featured["Close"]
        if not np.all(np.isfinite(ratio)) or (ratio <= 0).any():
            raise ValueError(
                "Return targets require strictly positive current and future "
                "close prices"
            )
        featured["Simple_Return"] = ratio - 1.0
        featured["Log_Return"] = np.log(ratio)
        dataset.featured_df = featured

        development, holdout, holdout_info = split_development_holdout(
            dataset, active
        )
        folds, fold_info = generate_walk_forward_folds(
            development, active
        )

        return {
            "symbol": normalized,
            "raw_data": raw_data,
            "clean_data": clean_data,
            "dataset": dataset,
            "development": development,
            "holdout": holdout,
            "holdout_info": holdout_info,
            "folds": folds,
            "fold_info": fold_info,
        }

    # ------------------------------------------------------------------
    # Target-specific fitting and reconstruction
    # ------------------------------------------------------------------
    @staticmethod
    def _target_values(frame: pd.DataFrame, family: str) -> np.ndarray:
        if family == FAMILY_ABSOLUTE:
            return frame["Next_Day_Close"].to_numpy(dtype=float)
        if family == FAMILY_SIMPLE:
            return frame["Simple_Return"].to_numpy(dtype=float)
        if family == FAMILY_LOG:
            return frame["Log_Return"].to_numpy(dtype=float)
        raise ValueError(f"Unknown family: {family}")

    @staticmethod
    def _reconstruct_prices(
        family: str,
        current_close: np.ndarray,
        predictions: np.ndarray,
    ) -> np.ndarray:
        if family == FAMILY_ABSOLUTE:
            return np.asarray(predictions, dtype=float)
        if family == FAMILY_SIMPLE:
            return current_close * (1.0 + np.asarray(predictions, dtype=float))
        if family == FAMILY_LOG:
            return current_close * np.exp(np.asarray(predictions, dtype=float))
        raise ValueError(f"Unknown family: {family}")

    def _evaluate_family(
        self,
        family: str,
        train: pd.DataFrame,
        validation: pd.DataFrame,
        feature_columns: Sequence[str],
        label: str,
    ) -> Dict[str, Any]:
        X_train = train[list(feature_columns)].to_numpy(dtype=float)
        y_train = self._target_values(train, family)
        X_validation = validation[list(feature_columns)].to_numpy(dtype=float)
        current_close = validation["Close"].to_numpy(dtype=float)
        actual_close = validation["Next_Day_Close"].to_numpy(dtype=float)
        actual_return = (
            actual_close / current_close - 1.0
        )
        actual_log_return = np.log(actual_close / current_close)

        raw_predictions, diagnostics = _fit_models_for_fold(
            model_factories=self.model_factories,
            X_train=X_train,
            y_train=y_train,
            X_validation=X_validation,
            validation=validation,
            feature_columns=feature_columns,
        )

        # The zero-return baseline is identical in all families: predict no
        # movement and reconstruct the current close. Absolute-price models
        # predict a price directly, so their baseline prediction is current
        # close rather than a zero price.
        raw_predictions = dict(raw_predictions)
        if family == FAMILY_ABSOLUTE:
            baseline_raw = current_close.copy()
        else:
            baseline_raw = np.zeros(len(validation), dtype=float)
        raw_predictions[ZERO_RETURN_NAME] = baseline_raw
        diagnostics = dict(diagnostics)
        diagnostics[ZERO_RETURN_NAME] = {
            "status": "ok",
            "train_samples": 0,
            "train_features": int(X_train.shape[1]),
            "target_formulation": family,
        }

        component_predictions = [
            raw_predictions[name] for name in MODEL_NAMES
        ]
        if all(prediction is not None for prediction in component_predictions):
            ensemble_raw = np.mean(
                np.vstack(component_predictions), axis=0
            )
            raw_predictions[ENSEMBLE_NAME] = ensemble_raw
            diagnostics[ENSEMBLE_NAME] = {
                "status": "ok",
                "components": list(MODEL_NAMES),
                "weights": {
                    name: round(1.0 / len(MODEL_NAMES), 6)
                    for name in MODEL_NAMES
                },
                "train_samples": int(X_train.shape[0]),
                "train_features": int(X_train.shape[1]),
                "target_formulation": family,
            }
        else:
            raw_predictions[ENSEMBLE_NAME] = None
            diagnostics[ENSEMBLE_NAME] = {
                "status": "unavailable",
                "error": "One or more component models failed",
                "components": list(MODEL_NAMES),
                "train_samples": int(X_train.shape[0]),
                "train_features": int(X_train.shape[1]),
                "target_formulation": family,
            }

        candidates: Dict[str, Dict[str, Any]] = {}
        for name in CANDIDATE_NAMES:
            raw_prediction = raw_predictions.get(name)
            entry = dict(diagnostics.get(name, {"status": "failed"}))
            entry["target_formulation"] = family
            if raw_prediction is None:
                entry["status"] = entry.get("status", "failed")
                entry["return_metrics"] = None
                entry["price_metrics"] = None
                entry["predictions"] = None
                candidates[name] = entry
                continue

            raw_prediction = np.asarray(raw_prediction, dtype=float).reshape(-1)
            if len(raw_prediction) != len(validation):
                entry["status"] = "failed"
                entry["error"] = "Prediction length does not match validation"
                entry["return_metrics"] = None
                entry["price_metrics"] = None
                entry["predictions"] = None
                candidates[name] = entry
                continue

            reconstructed = self._reconstruct_prices(
                family, current_close, raw_prediction
            )
            finite_mask = np.isfinite(reconstructed) & np.isfinite(
                raw_prediction
            )
            if not np.all(finite_mask):
                entry["status"] = "failed"
                entry["error"] = "Non-finite return or reconstructed price"
                entry["return_metrics"] = None
                entry["price_metrics"] = None
                entry["predictions"] = None
                candidates[name] = entry
                continue

            predicted_return = (
                raw_prediction
                if family != FAMILY_ABSOLUTE
                else reconstructed / current_close - 1.0
            )
            if family == FAMILY_LOG:
                predicted_return = np.exp(raw_prediction) - 1.0
                target_return_for_metrics = actual_return
                predicted_log_return = raw_prediction
            else:
                target_return_for_metrics = actual_return
                predicted_log_return = None

            return_metrics = calculate_return_metrics(
                target_return_for_metrics, predicted_return
            )
            price_metrics = calculate_metrics(
                actual_close, reconstructed, current_close
            )

            entry.update(
                {
                    "status": "ok",
                    "return_metrics": return_metrics,
                    "price_metrics": price_metrics,
                    "predictions": {
                        "target_scale": [
                            float(value) for value in raw_prediction.tolist()
                        ],
                        "predicted_return": [
                            float(value) for value in predicted_return.tolist()
                        ],
                        "reconstructed_close": [
                            float(value) for value in reconstructed.tolist()
                        ],
                        "actual_return": [
                            float(value) for value in actual_return.tolist()
                        ],
                    },
                    "nonpositive_reconstructed_prices": int(
                        np.count_nonzero(reconstructed <= 0)
                    ),
                }
            )
            if family == FAMILY_LOG:
                entry["log_return_metrics"] = calculate_return_metrics(
                    actual_log_return, predicted_log_return
                )
            candidates[name] = entry

        errors = [
            {
                "model": name,
                "status": entry.get("status"),
                "error": entry.get("error"),
            }
            for name, entry in candidates.items()
            if entry.get("status") != "ok"
        ]
        all_required_ok = all(
            candidates[name].get("status") == "ok"
            for name in MODEL_NAMES + (ENSEMBLE_NAME,)
        )
        any_ok = any(
            entry.get("status") == "ok" for entry in candidates.values()
        )
        status = "ok" if all_required_ok else ("partial" if any_ok else "failed")

        baseline = candidates[ZERO_RETURN_NAME]
        comparison = {
            name: compare_metrics_to_baseline(
                entry["price_metrics"], baseline["price_metrics"]
            )
            for name, entry in candidates.items()
            if name != ZERO_RETURN_NAME
            and entry.get("price_metrics") is not None
        }

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
            "validation": {
                "samples": int(len(validation)),
                "start": _iso_date(validation["Date"].iloc[0]),
                "end": _iso_date(validation["Date"].iloc[-1]),
                "target_start": _iso_date(
                    validation["Target_Date"].iloc[0]
                ),
                "target_end": _iso_date(
                    validation["Target_Date"].iloc[-1]
                ),
                "dates": [
                    _iso_date(value) for value in validation["Date"].tolist()
                ],
                "target_dates": [
                    _iso_date(value)
                    for value in validation["Target_Date"].tolist()
                ],
                "current_close": [
                    float(value) for value in current_close.tolist()
                ],
                "actual_next_close": [
                    float(value) for value in actual_close.tolist()
                ],
            },
            "models": candidates,
            "baseline_comparison": comparison,
        }

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    @staticmethod
    def _rank_candidates(
        candidates: Mapping[str, Dict[str, Any]],
        metric_path: Sequence[str],
    ) -> List[Dict[str, Any]]:
        ranked: List[Tuple[float, str]] = []
        for name, entry in candidates.items():
            value: Any = entry
            for key in metric_path:
                value = value.get(key) if isinstance(value, dict) else None
            if value is None:
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric):
                ranked.append((numeric, name))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [
            {
                "rank": index,
                "model": name,
                "label": LABELS.get(name, name),
                "price_metrics": candidates[name].get("price_metrics"),
                "return_metrics": candidates[name].get("return_metrics"),
            }
            for index, (_, name) in enumerate(ranked, start=1)
        ]

    def _aggregate_family(
        self,
        family_reports: List[Dict[str, Any]],
        family: str,
    ) -> Dict[str, Any]:
        """Pool predictions across folds for each candidate."""
        aggregate: Dict[str, Any] = {}
        for name in CANDIDATE_NAMES:
            successful = [
                report
                for report in family_reports
                if report["models"][name].get("status") == "ok"
            ]
            if len(successful) != len(family_reports):
                aggregate[name] = {
                    "status": "incomplete",
                    "folds_evaluated": len(successful),
                    "metrics": None,
                    "label": LABELS.get(name, name),
                }
                continue

            actual_close = np.concatenate(
                [
                    np.asarray(
                        report["validation"]["actual_next_close"], dtype=float
                    )
                    for report in family_reports
                ]
            )
            current_close = np.concatenate(
                [
                    np.asarray(
                        report["validation"]["current_close"], dtype=float
                    )
                    for report in family_reports
                ]
            )
            reconstructed = np.concatenate(
                [
                    np.asarray(
                        report["models"][name]["predictions"][
                            "reconstructed_close"
                        ],
                        dtype=float,
                    )
                    for report in family_reports
                ]
            )
            predicted_return = np.concatenate(
                [
                    np.asarray(
                        report["models"][name]["predictions"][
                            "predicted_return"
                        ],
                        dtype=float,
                    )
                    for report in family_reports
                ]
            )
            actual_return = actual_close / current_close - 1.0

            return_metrics = calculate_return_metrics(
                actual_return, predicted_return
            )
            price_metrics = calculate_metrics(
                actual_close, reconstructed, current_close
            )
            aggregate[name] = {
                "status": "comparable",
                "folds_evaluated": len(successful),
                "label": LABELS.get(name, name),
                "return_metrics": return_metrics,
                "price_metrics": price_metrics,
                "validation_samples": int(len(actual_close)),
            }

        baseline = aggregate[ZERO_RETURN_NAME]
        baseline_price = baseline.get("price_metrics")
        comparison = {
            name: compare_metrics_to_baseline(
                entry["price_metrics"], baseline_price
            )
            for name, entry in aggregate.items()
            if name != ZERO_RETURN_NAME
            and entry.get("price_metrics") is not None
            and baseline_price is not None
        }
        ranking = self._rank_candidates(
            aggregate, ("price_metrics", "rmse")
        )
        return {
            "family": family,
            "models": aggregate,
            "baseline_comparison": comparison,
            "ranking_by_price_rmse": ranking,
            "best_by_price_rmse": ranking[0]["model"] if ranking else None,
        }

    def _family_holdout(
        self,
        family: str,
        train: pd.DataFrame,
        holdout: pd.DataFrame,
        feature_columns: Sequence[str],
    ) -> Dict[str, Any]:
        report = self._evaluate_family(
            family=family,
            train=train,
            validation=holdout,
            feature_columns=feature_columns,
            label="final_holdout",
        )
        ranking = self._rank_candidates(
            report["models"], ("price_metrics", "rmse")
        )
        report["ranking_by_price_rmse"] = ranking
        report["best_by_price_rmse"] = (
            ranking[0]["model"] if ranking else None
        )
        report["selection_locked_before_holdout"] = True
        return report

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------
    def evaluate_symbol(
        self,
        symbol: str,
        config: Optional[EvaluationConfig] = None,
        write_report: bool = True,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        active = config or self.config
        prepared = self.prepare_symbol(symbol, active)
        normalized = prepared["symbol"]
        dataset: EvaluationDataset = prepared["dataset"]
        development = prepared["development"]
        holdout = prepared["holdout"]
        holdout_info = prepared["holdout_info"]
        folds = prepared["folds"]
        fold_info = prepared["fold_info"]
        feature_columns = dataset.feature_columns

        family_fold_reports: Dict[str, List[Dict[str, Any]]] = {
            family: [] for family in FAMILIES
        }
        for fold in folds:
            train = development.iloc[fold.train_indices]
            validation = development.iloc[fold.validation_indices]
            for family in FAMILIES:
                report = self._evaluate_family(
                    family=family,
                    train=train,
                    validation=validation,
                    feature_columns=feature_columns,
                    label=f"fold_{fold.fold}",
                )
                report["fold"] = fold.fold
                report["train"]["start"] = _iso_date(fold.train_start)
                report["train"]["end"] = _iso_date(fold.train_end)
                report["train"]["target_start"] = _iso_date(
                    fold.train_target_start
                )
                report["train"]["target_end"] = _iso_date(
                    fold.train_target_end
                )
                report["validation"]["start"] = _iso_date(
                    fold.validation_start
                )
                report["validation"]["end"] = _iso_date(
                    fold.validation_end
                )
                report["validation"]["target_start"] = _iso_date(
                    fold.validation_target_start
                )
                report["validation"]["target_end"] = _iso_date(
                    fold.validation_target_end
                )
                family_fold_reports[family].append(report)

        # Holdout training boundary is fixed before any holdout comparison.
        holdout_target_start = holdout["Target_Date"].iloc[0]
        holdout_train_end = int(
            np.count_nonzero(
                (
                    development["Target_Date"] < holdout_target_start
                ).to_numpy()
            )
        )
        holdout_train = development.iloc[:holdout_train_end]

        families: Dict[str, Any] = {}
        for family in FAMILIES:
            aggregated = self._aggregate_family(
                family_fold_reports[family], family
            )
            holdout_report = self._family_holdout(
                family, holdout_train, holdout, feature_columns
            )
            families[family] = {
                "target_formulation": family,
                "folds": family_fold_reports[family],
                "aggregated": aggregated,
                "final_holdout": holdout_report,
                "folds_evaluated": len(family_fold_reports[family]),
            }

        # Final comparison is performed only after the holdout metrics are
        # recorded for all families. No hyperparameter or weight is tuned.
        holdout_rows = []
        for family in FAMILIES:
            best_name = families[family]["final_holdout"][
                "best_by_price_rmse"
            ]
            best_entry = (
                families[family]["final_holdout"]["models"].get(best_name, {})
                if best_name
                else {}
            )
            baseline = families[family]["final_holdout"]["models"][
                ZERO_RETURN_NAME
            ]
            holdout_rows.append(
                {
                    "family": family,
                    "best_model_by_price_rmse": best_name,
                    "best_model_price_metrics": best_entry.get(
                        "price_metrics"
                    ),
                    "best_model_return_metrics": best_entry.get(
                        "return_metrics"
                    ),
                    "zero_return_price_metrics": baseline.get(
                        "price_metrics"
                    ),
                    "zero_return_return_metrics": baseline.get(
                        "return_metrics"
                    ),
                }
            )

        price_ranked = sorted(
            [
                row
                for row in holdout_rows
                if row["best_model_price_metrics"] is not None
                and row["best_model_price_metrics"].get("rmse") is not None
            ],
            key=lambda row: (
                row["best_model_price_metrics"]["rmse"],
                row["family"],
            ),
        )
        return_ranked = sorted(
            [
                row
                for row in holdout_rows
                if row["best_model_return_metrics"] is not None
                and row["best_model_return_metrics"].get("rmse") is not None
            ],
            key=lambda row: (
                row["best_model_return_metrics"]["rmse"],
                row["family"],
            ),
        )
        best_price_family = price_ranked[0]["family"] if price_ranked else None
        best_return_family = return_ranked[0]["family"] if return_ranked else None

        absolute_baseline_rmse = families[FAMILY_ABSOLUTE]["final_holdout"][
            "models"
        ][ZERO_RETURN_NAME]["price_metrics"]["rmse"]
        best_price_rmse = (
            price_ranked[0]["best_model_price_metrics"]["rmse"]
            if price_ranked
            else None
        )
        recommendation = (
            "No return-based family showed a holdout price-RMSE advantage "
            "over the zero-return persistence baseline or the absolute-price "
            "family. Keep production forecasting unchanged and treat return "
            "targets as experimental."
            if best_price_family in {FAMILY_ABSOLUTE, None}
            or best_price_rmse is None
            or absolute_baseline_rmse is None
            or best_price_rmse >= absolute_baseline_rmse
            else "The final holdout favors a return-based family on reconstructed "
            "price RMSE. This is a single holdout result and should be "
            "validated on additional periods before any production change."
        )

        warnings: List[str] = []
        if fold_info["folds_reduced"]:
            warnings.append(
                "Requested folds were reduced because of available history."
            )
        if holdout_info["holdout_size_adjusted"]:
            warnings.append(
                "The final holdout size was adjusted to preserve development "
                "history."
            )
        for family in FAMILIES:
            if any(
                fold["status"] != "ok"
                for fold in family_fold_reports[family]
            ):
                warnings.append(
                    f"{family}: one or more folds had model failures; see "
                    "the fold error entries."
                )
            if families[family]["final_holdout"]["status"] != "ok":
                warnings.append(
                    f"{family}: one or more final-holdout model fits failed."
                )

        report: Dict[str, Any] = {
            "schema_version": "1.0",
            "experiment": "return_vs_absolute_price",
            "symbol": normalized,
            "generated_at": self.now_provider().astimezone(timezone.utc).isoformat(),
            "status": "completed",
            "production_inference_changed": False,
            "config": active.to_dict(),
            "methodology": {
                "targets": {
                    FAMILY_ABSOLUTE: "Next_Day_Close",
                    FAMILY_SIMPLE: "Close[t+1] / Close[t] - 1",
                    FAMILY_LOG: "log(Close[t+1] / Close[t])",
                },
                "reconstruction": {
                    FAMILY_ABSOLUTE: "predicted close directly",
                    FAMILY_SIMPLE: "current_close * (1 + predicted_return)",
                    FAMILY_LOG: "current_close * exp(predicted_log_return)",
                },
                "baseline": (
                    "zero-return persistence: predicted return = 0 and "
                    "reconstructed close = current close"
                ),
                "folds": (
                    "identical chronological expanding-window folds and final "
                    "holdout boundaries as the Phase 2 evaluation, generated "
                    "from the same clean data and EvaluationConfig"
                ),
                "selection": (
                    "no model or weight is selected on the final holdout; "
                    "development folds and the holdout are reported separately"
                ),
                "preprocessing": (
                    "fresh model instances and a fresh SVR StandardScaler per "
                    "family, fold, and training prefix"
                ),
                "shuffle": False,
                "directional_semantics": (
                    "zero predicted return is an abstention; directional "
                    "accuracy uses non-zero predictions on actual moving days "
                    "and signal coverage reports abstention frequency"
                ),
            },
            "data": {
                "source": "yfinance",
                "period": active.period,
                "raw_rows": int(len(prepared["raw_data"])),
                "clean_rows": int(len(prepared["clean_data"])),
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
                "feature_columns": list(feature_columns),
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
            "fold_generation": fold_info,
            "families": families,
            "final_holdout_comparison": {
                "rows": holdout_rows,
                "ranking_by_best_model_price_rmse": price_ranked,
                "ranking_by_best_model_return_rmse": return_ranked,
                "best_family_by_price_rmse": best_price_family,
                "best_family_by_return_rmse": best_return_family,
                "absolute_family_zero_return_price_rmse": (
                    absolute_baseline_rmse
                ),
                "recommendation": recommendation,
            },
            "warnings": warnings,
            "limitations": [
                "Return experiments use the same historical yfinance snapshot "
                "and may differ if vendor data or the current session changes.",
                "A return forecast can be numerically valid but economically "
                "unreliable; reconstructed prices are not trading advice.",
                "The final holdout is one chronological period and is reported "
                "after development evaluation, not used for tuning.",
                "This experiment does not model transaction costs, slippage, "
                "or portfolio construction.",
                "No production model or inference path was changed.",
            ],
        }
        safe_report = _json_safe(report)
        if write_report:
            path = self.save_report(safe_report, output_dir=output_dir)
            safe_report["report_path"] = path
        return safe_report

    def save_report(
        self,
        report: Mapping[str, Any],
        output_dir: Optional[str] = None,
    ) -> str:
        directory = output_dir or self.report_dir
        os.makedirs(directory, exist_ok=True)
        symbol = str(report.get("symbol", "symbol"))
        path = os.path.join(
            directory, symbol.replace(".", "_") + "_return_forecasting.json"
        )
        serialized = json.dumps(
            _json_safe(dict(report)),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized + "\n")
        return path


return_forecasting_service = ReturnForecastingService()
