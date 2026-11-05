"""File-backed model registry with versioned artifacts and activation control.

Research retraining writes only under ``model_registry``. It never overwrites
``saved_models`` and never mutates the currently active production artifacts.
A newly trained version is a candidate until an explicit, audited activation.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional

import joblib
import numpy as np

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


MODEL_FACTORIES = {
    "linear_regression": LinearRegressionModel,
    "decision_tree": DecisionTreeModel,
    "random_forest": RandomForestModel,
    "svr": SVRModel,
    "xgboost": XGBoostModel,
}
MODEL_NAMES = tuple(MODEL_FACTORIES)
MODEL_LABELS = {
    "linear_regression": "Linear Regression",
    "decision_tree": "Decision Tree",
    "random_forest": "Random Forest",
    "svr": "Support Vector Regressor (SVR)",
    "xgboost": "XGBoost",
}
ENSEMBLE_NAME = "ensemble_equal_weight"
SCHEMA_VERSION = "1.0"
ARTIFACT_SCHEMA_VERSION = "1.0"
TARGET_FORMULATION = "absolute_price"


class ModelRegistryError(ValueError):
    """A registry validation or artifact error."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_hyperparameters(model: Any) -> Dict[str, Any]:
    estimator = getattr(model, "model", None)
    params: Dict[str, Any] = {}
    if estimator is not None and hasattr(estimator, "get_params"):
        try:
            raw = estimator.get_params(deep=False)
            for key, value in raw.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    params[key] = value
                else:
                    params[key] = repr(value)
        except Exception:  # noqa: BLE001 - metadata must not break training
            params = {}
    return params


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return repr(value)


def _safe_json(value: Any) -> Any:
    return json.loads(json.dumps(value, default=_json_default))


class ModelRegistryService:
    _lock = threading.RLock()

    def __init__(
        self,
        registry_dir: Optional[str] = None,
        data_service_override: Any = None,
        feature_engineering_override: Any = None,
        model_factories: Optional[Mapping[str, Callable[[], Any]]] = None,
        now_provider: Optional[Callable[[], str]] = None,
    ) -> None:
        self.registry_dir = registry_dir or settings.MODEL_REGISTRY_DIR
        self.registry_path = os.path.join(self.registry_dir, "registry.json")
        self.audit_path = os.path.join(self.registry_dir, "audit.jsonl")
        self.data_service = data_service_override or data_service
        self.feature_engineering = (
            feature_engineering_override or feature_engineering
        )
        self.model_factories = dict(model_factories or MODEL_FACTORIES)
        missing = [name for name in MODEL_NAMES if name not in self.model_factories]
        if missing:
            raise ValueError("Missing model factories for: " + ", ".join(missing))
        self.now_provider = now_provider or _utc_now
        os.makedirs(self.registry_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Registry persistence
    # ------------------------------------------------------------------
    def _empty_registry(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "updated_at": None,
            "symbols": {},
        }

    def _load_registry(self) -> Dict[str, Any]:
        if not os.path.exists(self.registry_path):
            return self._empty_registry()
        with open(self.registry_path, encoding="utf-8") as handle:
            registry = json.load(handle)
        if not isinstance(registry, dict) or "symbols" not in registry:
            raise ModelRegistryError("Registry file has an invalid schema")
        return registry

    def _save_registry(self, registry: Mapping[str, Any]) -> None:
        os.makedirs(self.registry_dir, exist_ok=True)
        registry = dict(registry)
        registry["updated_at"] = self.now_provider()
        temporary = self.registry_path + ".tmp"
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                _safe_json(registry),
                handle,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            handle.write("\n")
        os.replace(temporary, self.registry_path)

    def _audit(self, event: str, **payload: Any) -> None:
        os.makedirs(self.registry_dir, exist_ok=True)
        record = {
            "event": event,
            "timestamp": self.now_provider(),
            **payload,
        }
        with open(self.audit_path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(_safe_json(record), sort_keys=True) + "\n")

    # ------------------------------------------------------------------
    # Read APIs
    # ------------------------------------------------------------------
    def get_registry(self) -> Dict[str, Any]:
        with self._lock:
            return _safe_json(self._load_registry())

    def get_symbol(self, symbol: str) -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        with self._lock:
            registry = self._load_registry()
            return _safe_json(
                registry.get("symbols", {}).get(normalized, {})
            )

    def list_versions(self, symbol: str) -> List[Dict[str, Any]]:
        symbol_state = self.get_symbol(symbol)
        versions: Dict[str, Any] = symbol_state.get("versions", {})
        return [
            _safe_json(version)
            for _, version in sorted(versions.items())
        ]

    def get_version(self, symbol: str, version: str) -> Dict[str, Any]:
        version_entry = self.get_symbol(symbol).get("versions", {}).get(
            version
        )
        if version_entry is None:
            raise ModelRegistryError(
                f"Version {version} does not exist for {symbol}"
            )
        return _safe_json(version_entry)

    def get_active(self, symbol: str) -> Optional[Dict[str, Any]]:
        state = self.get_symbol(symbol)
        active = state.get("active_version")
        if not active:
            return None
        return state.get("versions", {}).get(active)

    def summary(self) -> Dict[str, Any]:
        registry = self.get_registry()
        symbols = []
        for symbol, state in sorted(registry.get("symbols", {}).items()):
            versions = state.get("versions", {})
            symbols.append(
                {
                    "symbol": symbol,
                    "active_version": state.get("active_version"),
                    "version_count": len(versions),
                    "candidate_count": sum(
                        1
                        for version in versions.values()
                        if version.get("status") == "candidate"
                    ),
                    "last_updated": max(
                        (
                            version.get("created_at", "")
                            for version in versions.values()
                        ),
                        default=None,
                    ),
                }
            )
        return {
            "schema_version": registry.get("schema_version", SCHEMA_VERSION),
            "updated_at": registry.get("updated_at"),
            "symbols": symbols,
            "total_symbols": len(symbols),
            "total_versions": sum(
                item["version_count"] for item in symbols
            ),
        }

    # ------------------------------------------------------------------
    # Training and candidate creation
    # ------------------------------------------------------------------
    @staticmethod
    def _version_number(versions: Mapping[str, Any]) -> int:
        highest = 0
        for version in versions:
            if version.startswith("v") and version[1:].isdigit():
                highest = max(highest, int(version[1:]))
        return highest + 1

    def _artifact_dir(self, symbol: str, version: str) -> str:
        symbol_dir = symbol.replace(".", "_")
        return os.path.join(self.registry_dir, "artifacts", symbol_dir, version)

    def _relative_artifact_dir(self, symbol: str, version: str) -> str:
        return os.path.join(
            "artifacts", symbol.replace(".", "_"), version
        ).replace("\\", "/")

    def train_candidate(
        self,
        symbol: str,
        period: Optional[str] = None,
        notes: Optional[str] = None,
        actor: str = "system",
    ) -> Dict[str, Any]:
        """Train and save a candidate without touching active artifacts."""

        normalized = validate_symbol(symbol)
        period = period or settings.TRAINING_PERIOD
        with self._lock:
            registry = self._load_registry()
            symbol_state = registry.setdefault(
                "symbols",
                {},
            ).setdefault(
                normalized,
                {"active_version": None, "history": [], "versions": {}},
            )
            versions = symbol_state.setdefault("versions", {})
            next_version = f"v{self._version_number(versions)}"
            artifact_dir = self._artifact_dir(normalized, next_version)
            if os.path.exists(artifact_dir):
                raise ModelRegistryError(
                    f"Refusing to overwrite existing artifact directory: "
                    f"{artifact_dir}"
                )
            os.makedirs(artifact_dir, exist_ok=False)

        try:
            raw = self.data_service.fetch_stock_data(normalized, period)
            clean = self.data_service.clean_data(raw)
            featured = self.feature_engineering.transform(clean)
            feature_columns = list(
                self.feature_engineering.get_feature_columns()
            )
            if len(featured) < 80:
                raise ModelRegistryError(
                    "Not enough feature rows to train and validate a candidate"
                )
            split_index = int(
                len(featured) * (1 - settings.TRAIN_TEST_SPLIT)
            )
            if split_index <= 0 or split_index >= len(featured):
                raise ModelRegistryError(
                    "Not enough rows for a chronological candidate split"
                )
            train = featured.iloc[:split_index]
            test = featured.iloc[split_index:]
            X_train = train[feature_columns].to_numpy(dtype=float)
            y_train = train["Next_Day_Close"].to_numpy(dtype=float)
            X_test = test[feature_columns].to_numpy(dtype=float)
            y_test = test["Next_Day_Close"].to_numpy(dtype=float)
            current_close = test["Close"].to_numpy(dtype=float)

            artifacts: Dict[str, str] = {}
            models: Dict[str, Any] = {}
            metrics: Dict[str, Any] = {}
            diagnostics: Dict[str, Any] = {}
            model_predictions: List[np.ndarray] = []

            for name in MODEL_NAMES:
                factory = self.model_factories.get(name)
                if factory is None:
                    raise ModelRegistryError(
                        f"No model factory registered for {name}"
                    )
                model = factory()
                model.train(X_train, y_train)
                prediction = np.asarray(
                    model.predict(X_test), dtype=float
                ).reshape(-1)
                if len(prediction) != len(y_test):
                    raise ModelRegistryError(
                        f"{name} returned an unexpected prediction length"
                    )
                if not np.all(np.isfinite(prediction)):
                    raise ModelRegistryError(
                        f"{name} returned non-finite predictions"
                    )
                models[name] = model
                model_predictions.append(prediction)
                metrics[name] = calculate_metrics(
                    y_test, prediction, current_close
                )
                diagnostics[name] = {
                    "status": "ok",
                    "preprocessing": (
                        {
                            "name": "StandardScaler",
                            "fit_on": "candidate_training_rows_only",
                        }
                        if name == "svr"
                        else None
                    ),
                    "hyperparameters": _safe_hyperparameters(model),
                }
                artifact_name = f"{name}.pkl"
                joblib.dump(
                    model.model, os.path.join(artifact_dir, artifact_name)
                )
                artifacts[name] = artifact_name
                scaler = getattr(model, "get_scaler", None)
                if callable(scaler):
                    scaler_artifact = f"{name}_scaler.pkl"
                    joblib.dump(
                        scaler(),
                        os.path.join(artifact_dir, scaler_artifact),
                    )
                    artifacts[f"{name}_scaler"] = scaler_artifact

            ensemble_prediction = np.mean(
                np.vstack(model_predictions), axis=0
            )
            metrics[ENSEMBLE_NAME] = calculate_metrics(
                y_test, ensemble_prediction, current_close
            )
            baseline_prediction = current_close.copy()
            metrics["naive_persistence"] = calculate_metrics(
                y_test, baseline_prediction, current_close
            )
            baseline_metrics = metrics["naive_persistence"]
            baseline_comparison = {
                name: compare_metrics_to_baseline(value, baseline_metrics)
                for name, value in metrics.items()
                if name != "naive_persistence"
            }
            validation_metrics = {
                "models": metrics,
                "baseline_comparison": baseline_comparison,
                "best_model_by_rmse": min(
                    (
                        name
                        for name in MODEL_NAMES + (ENSEMBLE_NAME,)
                        if metrics.get(name, {}).get("rmse") is not None
                    ),
                    key=lambda name: metrics[name]["rmse"],
                    default=None,
                ),
                "split_method": "chronological holdout",
                "test_fraction": settings.TRAIN_TEST_SPLIT,
                "training_samples": int(len(train)),
                "testing_samples": int(len(test)),
                "test_start": str(test["Date"].iloc[0]),
                "test_end": str(test["Date"].iloc[-1]),
            }

            with self._lock:
                registry = self._load_registry()
                symbol_state = registry.setdefault(
                    "symbols", {}
                ).setdefault(
                    normalized,
                    {
                        "active_version": None,
                        "history": [],
                        "versions": {},
                    },
                )
                versions = symbol_state.setdefault("versions", {})
                current_active = symbol_state.get("active_version")
                active_version = versions.get(current_active) if current_active else None
                candidate_vs_active = None
                if active_version:
                    active_metrics = (
                        active_version.get("validation", {})
                        .get("models", {})
                        .get(ENSEMBLE_NAME)
                    )
                    candidate_vs_active = compare_metrics_to_baseline(
                        metrics[ENSEMBLE_NAME],
                        active_metrics or {},
                    )
                    candidate_vs_active["note"] = (
                        "Candidate validation RMSE compared with the active "
                        "version's stored validation RMSE."
                    )

                entry = {
                    "model_id": f"{normalized}:{next_version}",
                    "symbol": normalized,
                    "version": next_version,
                    "created_at": self.now_provider(),
                    "created_by": actor,
                    "status": "candidate",
                    "approved": False,
                    "approved_at": None,
                    "approved_by": None,
                    "target_formulation": TARGET_FORMULATION,
                    "feature_schema_version": ARTIFACT_SCHEMA_VERSION,
                    "feature_columns": feature_columns,
                    "period": period,
                    "training": {
                        "start": str(train["Date"].iloc[0]),
                        "end": str(train["Date"].iloc[-1]),
                        "samples": int(len(train)),
                        "test_fraction": settings.TRAIN_TEST_SPLIT,
                        "random_state": settings.RANDOM_STATE,
                    },
                    "validation": validation_metrics,
                    "candidate_vs_active": candidate_vs_active,
                    "artifacts": artifacts,
                    "artifact_dir": self._relative_artifact_dir(
                        normalized, next_version
                    ),
                    "artifact_compatibility": {
                        "schema_version": ARTIFACT_SCHEMA_VERSION,
                        "feature_columns": feature_columns,
                        "target_formulation": TARGET_FORMULATION,
                        "model_names": list(MODEL_NAMES),
                        "has_svr_scaler": "svr_scaler" in artifacts,
                    },
                    "diagnostics": diagnostics,
                    "notes": notes or "",
                    "production_artifact_unchanged": True,
                }
                versions[next_version] = entry
                symbol_state["history"] = list(symbol_state.get("history", [])) + [
                    next_version
                ]
                registry["symbols"][normalized] = symbol_state
                self._save_registry(registry)
                self._audit(
                    "candidate_created",
                    symbol=normalized,
                    version=next_version,
                    model_id=entry["model_id"],
                    actor=actor,
                )
                return _safe_json(entry)
        except Exception:
            # A failed candidate must not leave a partially usable version in
            # the registry. Artifacts are research-only and can be discarded.
            with self._lock:
                registry = self._load_registry()
                symbol_state = registry.get("symbols", {}).get(normalized, {})
                if next_version in symbol_state.get("versions", {}):
                    symbol_state["versions"].pop(next_version, None)
                    self._save_registry(registry)
            if os.path.exists(artifact_dir):
                shutil.rmtree(artifact_dir, ignore_errors=True)
            raise

    # ------------------------------------------------------------------
    # Approval, activation, rollback
    # ------------------------------------------------------------------
    def approve_version(
        self,
        symbol: str,
        version: str,
        approved_by: str = "admin",
        approved: bool = True,
    ) -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        with self._lock:
            registry = self._load_registry()
            symbol_state = registry.get("symbols", {}).get(normalized)
            if not symbol_state:
                raise ModelRegistryError(f"No registry entry for {normalized}")
            entry = symbol_state.get("versions", {}).get(version)
            if not entry:
                raise ModelRegistryError(
                    f"Version {version} does not exist for {normalized}"
                )
            entry["approved"] = bool(approved)
            entry["approved_at"] = self.now_provider() if approved else None
            entry["approved_by"] = approved_by if approved else None
            self._save_registry(registry)
            self._audit(
                "candidate_approved" if approved else "candidate_unapproved",
                symbol=normalized,
                version=version,
                actor=approved_by,
            )
            return _safe_json(entry)

    def activate_version(
        self,
        symbol: str,
        version: str,
        approved: bool = False,
        approved_by: str = "admin",
    ) -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        if not approved:
            raise ModelRegistryError(
                "Activation requires explicit approval (approved=true) by an "
                "authorized administrator"
            )
        with self._lock:
            registry = self._load_registry()
            symbol_state = registry.get("symbols", {}).get(normalized)
            if not symbol_state:
                raise ModelRegistryError(f"No registry entry for {normalized}")
            versions = symbol_state.get("versions", {})
            entry = versions.get(version)
            if not entry:
                raise ModelRegistryError(
                    f"Version {version} does not exist for {normalized}"
                )
            self._validate_artifacts(entry)
            previous = symbol_state.get("active_version")
            for other_version, other_entry in versions.items():
                if other_entry.get("status") == "active":
                    other_entry["status"] = "inactive"
            entry["approved"] = True
            entry["approved_at"] = entry.get("approved_at") or self.now_provider()
            entry["approved_by"] = entry.get("approved_by") or approved_by
            entry["status"] = "active"
            entry["activated_at"] = self.now_provider()
            entry["activated_by"] = approved_by
            symbol_state["active_version"] = version
            symbol_state["previous_active_version"] = previous
            activation_history = list(
                symbol_state.get("activation_history", [])
            )
            if not activation_history or activation_history[-1] != version:
                activation_history.append(version)
            symbol_state["activation_history"] = activation_history
            history = list(symbol_state.get("history", []))
            if version not in history:
                history.append(version)
            symbol_state["history"] = history
            registry["symbols"][normalized] = symbol_state
            self._save_registry(registry)
            self._audit(
                "version_activated",
                symbol=normalized,
                version=version,
                previous_version=previous,
                actor=approved_by,
            )
            return _safe_json(entry)

    def deactivate(self, symbol: str, actor: str = "admin") -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        with self._lock:
            registry = self._load_registry()
            symbol_state = registry.get("symbols", {}).get(normalized)
            if not symbol_state:
                raise ModelRegistryError(f"No registry entry for {normalized}")
            previous = symbol_state.get("active_version")
            if previous:
                entry = symbol_state.get("versions", {}).get(previous, {})
                entry["status"] = "inactive"
                entry["deactivated_at"] = self.now_provider()
            symbol_state["active_version"] = None
            registry["symbols"][normalized] = symbol_state
            self._save_registry(registry)
            self._audit(
                "version_deactivated",
                symbol=normalized,
                version=previous,
                actor=actor,
            )
            return {
                "symbol": normalized,
                "previous_active_version": previous,
                "active_version": None,
            }

    def rollback(self, symbol: str, actor: str = "admin") -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        with self._lock:
            registry = self._load_registry()
            symbol_state = registry.get("symbols", {}).get(normalized)
            if not symbol_state:
                raise ModelRegistryError(f"No registry entry for {normalized}")
            active = symbol_state.get("active_version")
            activation_history = list(
                symbol_state.get("activation_history", [])
            )
            candidates = [
                version
                for version in activation_history
                if version != active
            ]
            if not candidates:
                raise ModelRegistryError(
                    "No previously active version is available for rollback"
                )
            previous = candidates[-1]
            registry_entry = symbol_state["versions"][previous]
            self._validate_artifacts(registry_entry)
        return self.activate_version(
            normalized, previous, approved=True, approved_by=actor
        )

    # ------------------------------------------------------------------
    # Artifact loading and prediction
    # ------------------------------------------------------------------
    def _validate_artifacts(self, entry: Mapping[str, Any]) -> None:
        artifact_dir = os.path.realpath(
            os.path.join(self.registry_dir, entry.get("artifact_dir", ""))
        )
        registry_root = os.path.realpath(self.registry_dir)
        if artifact_dir != registry_root and not artifact_dir.startswith(
            registry_root + os.sep
        ):
            raise ModelRegistryError("Artifact path escapes the registry root")
        if not os.path.isdir(artifact_dir):
            raise ModelRegistryError(
                f"Artifact directory does not exist: {artifact_dir}"
            )
        compatibility = entry.get("artifact_compatibility", {})
        expected_features = list(
            self.feature_engineering.get_feature_columns()
        )
        if compatibility.get("feature_columns") != expected_features:
            raise ModelRegistryError(
                "Artifact feature schema is incompatible with the current "
                "feature engineering schema"
            )
        if compatibility.get("schema_version") != ARTIFACT_SCHEMA_VERSION:
            raise ModelRegistryError(
                "Artifact schema version is unsupported"
            )
        for name in MODEL_NAMES:
            artifact = entry.get("artifacts", {}).get(name)
            if not artifact:
                raise ModelRegistryError(f"Missing artifact for {name}")
            path = os.path.realpath(os.path.join(artifact_dir, artifact))
            if not path.startswith(artifact_dir + os.sep):
                raise ModelRegistryError("Artifact path escapes its version directory")
            if not os.path.exists(path):
                raise ModelRegistryError(f"Artifact does not exist: {artifact}")
        if not entry.get("artifacts", {}).get("svr_scaler"):
            raise ModelRegistryError("Missing SVR scaler artifact")

    def load_version_models(
        self, symbol: str, version: str
    ) -> Dict[str, Any]:
        entry = self.get_version(symbol, version)
        self._validate_artifacts(entry)
        artifact_dir = os.path.realpath(
            os.path.join(self.registry_dir, entry["artifact_dir"])
        )
        loaded: Dict[str, Any] = {}
        for name in MODEL_NAMES:
            factory = self.model_factories[name]
            model = factory()
            artifact_path = os.path.join(
                artifact_dir, entry["artifacts"][name]
            )
            model.model = joblib.load(artifact_path)
            if name == "svr":
                scaler_path = os.path.join(
                    artifact_dir, entry["artifacts"]["svr_scaler"]
                )
                model.scaler = joblib.load(scaler_path)
            loaded[name] = model
        return {
            "entry": entry,
            "models": loaded,
            "artifact_dir": artifact_dir,
        }

    def predict_with_active(self, symbol: str) -> Dict[str, Any]:
        normalized = validate_symbol(symbol)
        active = self.get_active(normalized)
        if not active:
            raise ModelRegistryError(
                f"No active registered model for {normalized}; train and "
                "explicitly activate a candidate first"
            )
        loaded = self.load_version_models(
            normalized, active["version"]
        )
        raw = self.data_service.fetch_stock_data(normalized, "6mo")
        clean = self.data_service.clean_data(raw)
        featured = self.feature_engineering.transform_features(clean)
        feature_columns = loaded["entry"]["feature_columns"]
        latest = featured.iloc[-1]
        vector = latest[feature_columns].to_numpy(dtype=float).reshape(1, -1)
        if not np.all(np.isfinite(vector)):
            raise ModelRegistryError(
                "Latest feature vector contains non-finite values"
            )
        current_price = float(latest["Close"])
        predictions: Dict[str, Any] = {}
        values: List[float] = []
        for name, model in loaded["models"].items():
            prediction = float(model.predict(vector)[0])
            if not np.isfinite(prediction):
                predictions[name] = {
                    "prediction": None,
                    "error": "Non-finite prediction",
                }
                continue
            predictions[name] = {"prediction": round(prediction, 4)}
            values.append(prediction)
        ensemble = round(float(np.mean(values)), 4) if values else None
        predicted_return = (
            ensemble / current_price - 1.0
            if ensemble is not None and current_price > 0
            else None
        )
        if predicted_return is None:
            signal = "N/A"
        elif predicted_return > 0.01:
            signal = "BUY"
        elif predicted_return < -0.01:
            signal = "SELL"
        else:
            signal = "HOLD"
        return {
            "symbol": normalized,
            "model_id": active["model_id"],
            "model_version": active["version"],
            "feature_timestamp": str(latest["Date"]),
            "current_price": round(current_price, 4),
            "predicted_price": ensemble,
            "predicted_return": (
                round(predicted_return, 8)
                if predicted_return is not None
                else None
            ),
            "signal": signal,
            "models": predictions,
            "ensemble_prediction": ensemble,
            "target_formulation": active.get("target_formulation"),
            "artifact_schema_version": active.get(
                "artifact_compatibility", {}
            ).get("schema_version"),
        }


model_registry_service = ModelRegistryService()
