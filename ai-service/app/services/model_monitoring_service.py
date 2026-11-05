"""Prediction tracking and monitoring for registered models.

Predictions are appended to per-symbol JSONL files under ``monitoring``. Once
the next session is available, actual outcomes can be attached and error,
directional accuracy, signal coverage, and feature-drift summaries recomputed.
This is monitoring evidence, not a guarantee of future performance.
"""

from __future__ import annotations

import json
import math
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from app.config import settings
from app.services.data_service import data_service, validate_symbol
from app.services.evaluation_metrics import calculate_metrics
from app.services.feature_engineering import feature_engineering


class ModelMonitoringService:
    _lock = threading.RLock()

    def __init__(
        self,
        monitoring_dir: Optional[str] = None,
        data_service_override: Any = None,
        feature_engineering_override: Any = None,
        now_provider: Optional[Callable[[], str]] = None,
    ) -> None:
        self.monitoring_dir = monitoring_dir or settings.MONITORING_DIR
        self.prediction_dir = os.path.join(
            self.monitoring_dir, "predictions"
        )
        self.data_service = data_service_override or data_service
        self.feature_engineering = (
            feature_engineering_override or feature_engineering
        )
        self.now_provider = now_provider or (
            lambda: datetime.now(timezone.utc).isoformat()
        )
        os.makedirs(self.prediction_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    def _path(self, symbol: str) -> str:
        normalized = validate_symbol(symbol)
        path = os.path.realpath(
            os.path.join(
                self.prediction_dir,
                normalized.replace(".", "_") + ".jsonl",
            )
        )
        root = os.path.realpath(self.prediction_dir)
        if not path.startswith(root + os.sep):
            raise ValueError("Prediction path escapes the monitoring root")
        return path

    def _read_records(self, symbol: str) -> List[Dict[str, Any]]:
        path = self._path(symbol)
        if not os.path.exists(path):
            return []
        records: List[Dict[str, Any]] = []
        with open(path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Corrupt prediction record at line {line_number}"
                    ) from exc
                if isinstance(record, dict):
                    records.append(record)
        return records

    def _write_records(
        self, symbol: str, records: Sequence[Mapping[str, Any]]
    ) -> None:
        path = self._path(symbol)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(
                    json.dumps(
                        record,
                        sort_keys=True,
                        allow_nan=False,
                    )
                    + "\n"
                )
        os.replace(temporary, path)

    # ------------------------------------------------------------------
    # Prediction tracking
    # ------------------------------------------------------------------
    def record_prediction(
        self,
        symbol: str,
        prediction: Mapping[str, Any],
        model_id: Optional[str] = None,
        model_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        current_price = prediction.get("current_price")
        predicted_price = prediction.get("predicted_price")
        if current_price is None or predicted_price is None:
            raise ValueError(
                "Prediction must include current_price and predicted_price"
            )
        current_price = float(current_price)
        predicted_price = float(predicted_price)
        if not math.isfinite(current_price) or current_price <= 0:
            raise ValueError("Prediction current_price must be positive")
        if not math.isfinite(predicted_price):
            raise ValueError("Prediction predicted_price must be finite")

        record = {
            "prediction_id": str(uuid.uuid4()),
            "symbol": normalized,
            "model_id": model_id or prediction.get("model_id"),
            "model_version": model_version
            or prediction.get("model_version"),
            "feature_timestamp": prediction.get("feature_timestamp"),
            "prediction_timestamp": self.now_provider(),
            "current_price": current_price,
            "predicted_price": predicted_price,
            "predicted_return": (
                float(prediction["predicted_return"])
                if prediction.get("predicted_return") is not None
                else predicted_price / current_price - 1.0
            ),
            "signal": prediction.get("signal"),
            "actual_price": None,
            "actual_date": None,
            "absolute_error": None,
            "prediction_error": None,
            "direction_correct": None,
            "status": "pending",
        }
        with self._lock:
            records = self._read_records(normalized)
            records.append(record)
            self._write_records(normalized, records)
        return record

    def update_actuals(
        self,
        symbol: str,
        market_data: Optional[pd.DataFrame] = None,
        period: str = "6mo",
    ) -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        if market_data is None:
            market_data = self.data_service.fetch_stock_data(
                normalized, period
            )
        clean = self.data_service.clean_data(market_data)
        clean = clean.sort_values("Date").reset_index(drop=True)
        date_to_index = {
            pd.Timestamp(value).date(): index
            for index, value in enumerate(clean["Date"])
        }

        updated = 0
        still_pending = 0
        with self._lock:
            records = self._read_records(normalized)
            for record in records:
                if record.get("status") != "pending":
                    continue
                feature_timestamp = record.get("feature_timestamp")
                if not feature_timestamp:
                    still_pending += 1
                    continue
                feature_date = pd.Timestamp(feature_timestamp).date()
                index = date_to_index.get(feature_date)
                if index is None or index + 1 >= len(clean):
                    still_pending += 1
                    continue
                next_row = clean.iloc[index + 1]
                actual = float(next_row["Close"])
                if not math.isfinite(actual):
                    still_pending += 1
                    continue
                current = float(record["current_price"])
                predicted = float(record["predicted_price"])
                direction_correct: Optional[bool] = None
                predicted_direction = np.sign(predicted - current)
                actual_direction = np.sign(actual - current)
                if predicted_direction != 0 and actual_direction != 0:
                    direction_correct = bool(
                        predicted_direction == actual_direction
                    )
                record.update(
                    {
                        "actual_price": actual,
                        "actual_date": str(
                            pd.Timestamp(next_row["Date"]).date()
                        ),
                        "absolute_error": abs(actual - predicted),
                        "prediction_error": actual - predicted,
                        "direction_correct": direction_correct,
                        "status": "completed",
                    }
                )
                updated += 1
            self._write_records(normalized, records)
        return {
            "symbol": normalized,
            "updated": updated,
            "still_pending": still_pending,
            "total_records": len(records),
        }

    # ------------------------------------------------------------------
    # Metrics and pagination
    # ------------------------------------------------------------------
    def list_predictions(
        self,
        symbol: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1 or page_size > 200:
            raise ValueError("page_size must be between 1 and 200")
        normalized = validate_symbol(symbol)
        records = self._read_records(normalized)
        records = list(reversed(records))
        start = (page - 1) * page_size
        end = start + page_size
        return {
            "symbol": normalized,
            "page": page,
            "page_size": page_size,
            "total": len(records),
            "total_pages": (len(records) + page_size - 1) // page_size,
            "items": records[start:end],
        }

    def _tracking_metrics(self, records: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
        completed = [
            record
            for record in records
            if record.get("status") == "completed"
            and record.get("actual_price") is not None
        ]
        if not completed:
            return {
                "completed_predictions": 0,
                "metrics": None,
                "message": "No completed predictions with actual outcomes yet.",
            }
        actual = np.array(
            [float(record["actual_price"]) for record in completed],
            dtype=float,
        )
        predicted = np.array(
            [float(record["predicted_price"]) for record in completed],
            dtype=float,
        )
        current = np.array(
            [float(record["current_price"]) for record in completed],
            dtype=float,
        )
        metrics = calculate_metrics(actual, predicted, current)
        errors = actual - predicted
        return {
            "completed_predictions": len(completed),
            "metrics": metrics,
            "mean_error": round(float(np.mean(errors)), 6),
            "mean_absolute_error": round(float(np.mean(np.abs(errors))), 6),
            "root_mean_squared_error": round(
                float(np.sqrt(np.mean(np.square(errors)))), 6
            ),
        }

    def _data_freshness(self, symbol: str) -> Dict[str, Any]:
        try:
            raw = self.data_service.fetch_stock_data(symbol, "6mo")
            clean = self.data_service.clean_data(raw)
            latest = clean.iloc[-1]
            return {
                "status": "ok",
                "latest_date": str(pd.Timestamp(latest["Date"]).date()),
                "rows": int(len(clean)),
                "latest_close": round(float(latest["Close"]), 6),
            }
        except Exception as exc:  # noqa: BLE001 - monitoring must report failures
            return {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
            }

    def _feature_drift(self, symbol: str) -> Dict[str, Any]:
        try:
            raw = self.data_service.fetch_stock_data(symbol, "2y")
            clean = self.data_service.clean_data(raw)
            features = self.feature_engineering.transform_features(clean)
            columns = list(self.feature_engineering.get_feature_columns())
            reference_rows = settings.DRIFT_REFERENCE_ROWS
            recent_rows = settings.DRIFT_RECENT_ROWS
            if len(features) < reference_rows + recent_rows:
                raise ValueError(
                    "Not enough feature rows for the configured drift windows"
                )
            reference = features.iloc[
                -(reference_rows + recent_rows):-recent_rows
            ][columns]
            recent = features.iloc[-recent_rows:][columns]
            drift_rows = []
            for column in columns:
                ref_values = reference[column].to_numpy(dtype=float)
                recent_values = recent[column].to_numpy(dtype=float)
                ref_values = ref_values[np.isfinite(ref_values)]
                recent_values = recent_values[np.isfinite(recent_values)]
                if len(ref_values) < 5 or len(recent_values) < 5:
                    drift_rows.append(
                        {
                            "feature": column,
                            "psi": None,
                            "standardized_mean_shift": None,
                            "drift_detected": False,
                            "reason": "insufficient finite values",
                        }
                    )
                    continue
                quantiles = np.unique(
                    np.quantile(ref_values, [0, 0.2, 0.4, 0.6, 0.8, 1.0])
                )
                if len(quantiles) < 2:
                    drift_rows.append(
                        {
                            "feature": column,
                            "psi": 0.0,
                            "standardized_mean_shift": 0.0,
                            "drift_detected": False,
                            "reason": "constant reference feature",
                        }
                    )
                    continue
                bins = quantiles.copy()
                bins[0] = -np.inf
                bins[-1] = np.inf
                ref_counts, _ = np.histogram(ref_values, bins=bins)
                recent_counts, _ = np.histogram(recent_values, bins=bins)
                ref_pct = np.clip(
                    ref_counts / max(ref_counts.sum(), 1),
                    1e-6,
                    None,
                )
                recent_pct = np.clip(
                    recent_counts / max(recent_counts.sum(), 1),
                    1e-6,
                    None,
                )
                psi = float(
                    np.sum(
                        (recent_pct - ref_pct) * np.log(recent_pct / ref_pct)
                    )
                )
                std = float(np.std(ref_values))
                shift = (
                    abs(float(np.mean(recent_values)) - float(np.mean(ref_values)))
                    / std
                    if std > 0
                    else 0.0
                )
                drift_rows.append(
                    {
                        "feature": column,
                        "psi": round(psi, 6),
                        "standardized_mean_shift": round(shift, 6),
                        "drift_detected": psi >= settings.DRIFT_PSI_THRESHOLD,
                    }
                )
            detected = [
                row["feature"] for row in drift_rows if row["drift_detected"]
            ]
            finite_psi = [
                row["psi"]
                for row in drift_rows
                if row["psi"] is not None
            ]
            return {
                "status": "ok",
                "method": (
                    "Population Stability Index (PSI) over reference quantile "
                    "bins, plus standardized mean shift; warning-only"
                ),
                "reference_rows": int(len(reference)),
                "recent_rows": int(len(recent)),
                "threshold": settings.DRIFT_PSI_THRESHOLD,
                "features": drift_rows,
                "detected_features": detected,
                "drift_detected": bool(detected),
                "max_psi": round(max(finite_psi), 6) if finite_psi else None,
                "warning": (
                    "Feature drift is a monitoring signal, not proof that "
                    "model performance has degraded or that a retrain is "
                    "required."
                ),
            }
        except Exception as exc:  # noqa: BLE001 - monitoring must report failures
            return {
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "drift_detected": None,
                "warning": "Drift could not be computed.",
            }

    def monitoring_summary(self, symbol: str) -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        records = self._read_records(normalized)
        completed = [
            record for record in records if record.get("status") == "completed"
        ]
        pending = [
            record for record in records if record.get("status") != "completed"
        ]
        versions: Dict[str, int] = {}
        for record in records:
            version = str(record.get("model_version") or "unknown")
            versions[version] = versions.get(version, 0) + 1
        metrics = self._tracking_metrics(records)
        latest = records[-1] if records else None
        return {
            "schema_version": "1.0",
            "symbol": normalized,
            "generated_at": self.now_provider(),
            "record_counts": {
                "total": len(records),
                "completed": len(completed),
                "pending": len(pending),
            },
            "model_versions": versions,
            "tracking_metrics": metrics,
            "latest_prediction": latest,
            "data_freshness": self._data_freshness(normalized),
            "warnings": (
                [
                    "Prediction tracking has not yet observed actual outcomes; "
                    "do not report performance metrics until predictions mature."
                ]
                if not completed
                else []
            ),
            "limitations": [
                "Monitoring metrics are computed only from completed, matched "
                "predictions and are not a guarantee of future performance.",
                "The monitoring store is append-oriented JSONL and is intended "
                "for this single-service research deployment.",
                "Feature drift is a warning signal, not proof of degradation.",
            ],
        }

    def drift_report(self, symbol: str) -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        drift = self._feature_drift(normalized)
        return {
            "schema_version": "1.0",
            "symbol": normalized,
            "generated_at": self.now_provider(),
            "data_freshness": self._data_freshness(normalized),
            "drift": drift,
            "warnings": (
                [drift["warning"]]
                if drift.get("warning")
                else []
            ),
        }


model_monitoring_service = ModelMonitoringService()
