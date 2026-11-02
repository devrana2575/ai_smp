from datetime import datetime, timezone

import numpy as np

from app.services.data_service import data_service
from app.services.feature_engineering import feature_engineering
from app.services.model_manager import model_manager
from app.models.linear_regression import LinearRegressionModel
from app.models.decision_tree import DecisionTreeModel
from app.models.random_forest import RandomForestModel
from app.models.svr_model import SVRModel
from app.models.xgboost_model import XGBoostModel
from app.config import settings


MODEL_LABELS = {
    "linear_regression": "Linear Regression",
    "decision_tree": "Decision Tree",
    "random_forest": "Random Forest",
    "svr": "Support Vector Regressor (SVR)",
    "xgboost": "XGBoost",
}


class PredictionService:
    def __init__(self):
        self.models = {
            "linear_regression": LinearRegressionModel,
            "decision_tree": DecisionTreeModel,
            "random_forest": RandomForestModel,
            "svr": SVRModel,
            "xgboost": XGBoostModel,
        }

    def _prepare_data(self, symbol: str, period: str = None):
        if period is None:
            period = settings.TRAINING_PERIOD

        raw_df = data_service.fetch_stock_data(symbol, period)
        clean_df = data_service.clean_data(raw_df)
        featured_df = feature_engineering.transform(clean_df)

        feature_cols = feature_engineering.get_feature_columns()
        X = featured_df[feature_cols].values
        y = featured_df["Next_Day_Close"].values

        split_index = int(len(X) * (1 - settings.TRAIN_TEST_SPLIT))
        if split_index <= 0 or split_index >= len(X):
            raise ValueError("Not enough data to create chronological train/test splits")

        return (
            X[:split_index],
            X[split_index:],
            y[:split_index],
            y[split_index:],
        ), featured_df

    def _model_label(self, model_name: str) -> str:
        return MODEL_LABELS.get(model_name, model_name.replace("_", " ").title())

    def _unpack_metrics(self, stored_metrics: dict) -> tuple:
        if not isinstance(stored_metrics, dict):
            return {}, {}

        if isinstance(stored_metrics.get("models"), dict):
            metadata = {k: v for k, v in stored_metrics.items() if k != "models"}
            return stored_metrics["models"], metadata

        return stored_metrics, {}

    def _build_metrics_payload(
        self,
        symbol: str,
        period: str,
        results: dict,
        training_samples: int,
        testing_samples: int,
        trained_at: str = None,
    ) -> dict:
        return {
            "symbol": symbol,
            "period": period,
            "trained_at": trained_at or datetime.now(timezone.utc).isoformat(),
            "training_samples": training_samples,
            "testing_samples": testing_samples,
            "split_method": "chronological",
            "models": results,
        }

    def train_all_models(self, symbol: str, period: str = None) -> dict:
        period = period or settings.TRAINING_PERIOD
        (X_train, X_test, y_train, y_test), featured_df = self._prepare_data(symbol, period)
        trained_at = datetime.now(timezone.utc).isoformat()

        results = {}

        for name, ModelClass in self.models.items():
            model_instance = ModelClass()
            model_instance.train(X_train, y_train)
            metrics = model_instance.evaluate(X_test, y_test)

            if hasattr(model_instance, "get_scaler"):
                model_manager.save_model(symbol, name, model_instance.model, model_instance.get_scaler())
            else:
                model_manager.save_model(symbol, name, model_instance.model)

            results[name] = {
                "metrics": metrics,
                "trained": True,
            }

        model_manager.save_metrics(
            symbol,
            self._build_metrics_payload(
                symbol,
                period,
                results,
                len(X_train),
                len(X_test),
                trained_at,
            ),
        )
        model_manager.save_evaluation_data(
            symbol,
            {
                "symbol": symbol,
                "period": period,
                "trained_at": trained_at,
                "training_samples": len(X_train),
                "testing_samples": len(X_test),
                "split_method": "chronological",
                "X_test": X_test,
                "y_test": y_test,
            },
        )

        best_model = max(results, key=lambda name: results[name]["metrics"]["r2_score"])

        return {
            "symbol": symbol,
            "models": results,
            "training_samples": len(X_train),
            "testing_samples": len(X_test),
            "feature_columns": feature_engineering.get_feature_columns(),
            "split_method": "chronological",
            "best_model": best_model,
            "best_model_label": self._model_label(best_model),
            "best_r2_score": results[best_model]["metrics"]["r2_score"],
        }

    def evaluate_saved_models(self, symbol: str, period: str = None) -> dict:
        evaluation_data = model_manager.load_evaluation_data(symbol)

        if evaluation_data is None:
            cached_evaluation = self.get_evaluation(symbol)
            cached_evaluation["message"] = (
                "Saved test-set data is unavailable. Retrain the models to "
                "enable fresh evaluation."
            )
            return cached_evaluation

        X_test = evaluation_data["X_test"]
        y_test = evaluation_data["y_test"]
        results = {}

        for name, ModelClass in self.models.items():
            saved_model = model_manager.load_model(symbol, name)
            if saved_model is None:
                continue

            model_instance = ModelClass()
            model_instance.model = saved_model

            if hasattr(model_instance, "scaler"):
                scaler = model_manager.load_scaler(symbol, name)
                if scaler is None:
                    continue
                model_instance.scaler = scaler

            metrics = model_instance.evaluate(X_test, y_test)
            results[name] = {
                "metrics": metrics,
                "trained": True,
            }

        if not results:
            return {
                "symbol": symbol,
                "evaluation": None,
                "has_evaluation": False,
                "message": "No trained models found",
            }

        model_manager.save_metrics(
            symbol,
            self._build_metrics_payload(
                symbol,
                evaluation_data.get("period") or period or settings.TRAINING_PERIOD,
                results,
                evaluation_data.get("training_samples", 0),
                evaluation_data.get("testing_samples", len(X_test)),
                evaluation_data.get("trained_at"),
            ),
        )

        return self.get_evaluation(symbol)

    def predict(self, symbol: str) -> dict:
        raw_df = data_service.fetch_stock_data(symbol, "6mo")
        clean_df = data_service.clean_data(raw_df)
        featured_df = feature_engineering.transform(clean_df)

        feature_cols = feature_engineering.get_feature_columns()
        latest_data = featured_df[feature_cols].values[-1:].copy()

        current_price = float(clean_df["Close"].iloc[-1])

        predictions = {}
        model_predictions = []

        for name in self.models.keys():
            model = model_manager.load_model(symbol, name)
            if model is None:
                predictions[name] = {"prediction": None, "error": "Model not trained"}
                continue

            if name == "svr":
                scaler = model_manager.load_scaler(symbol, name)
                if scaler is not None:
                    from sklearn.preprocessing import StandardScaler
                    scaled_data = scaler.transform(latest_data)
                    pred = float(model.predict(scaled_data)[0])
                else:
                    pred = float(model.predict(latest_data)[0])
            else:
                pred = float(model.predict(latest_data)[0])

            predictions[name] = {"prediction": round(pred, 2)}
            model_predictions.append(pred)

        ensemble_prediction = round(float(np.mean(model_predictions)), 2) if model_predictions else None

        if ensemble_prediction and current_price:
            diff_pct = ((ensemble_prediction - current_price) / current_price) * 100
            if diff_pct > 1:
                signal = "BUY"
            elif diff_pct < -1:
                signal = "SELL"
            else:
                signal = "HOLD"
        else:
            signal = "N/A"

        return {
            "symbol": symbol,
            "current_price": round(current_price, 2),
            "predicted_price": ensemble_prediction,
            "signal": signal,
            "models": predictions,
            "ensemble_prediction": ensemble_prediction,
        }

    def get_model_status(self, symbol: str) -> dict:
        return model_manager.get_all_models_status(symbol)

    def get_evaluation(self, symbol: str) -> dict:
        stored_metrics = model_manager.load_metrics(symbol)
        models, metadata = self._unpack_metrics(stored_metrics)

        evaluation = {}
        for name, data in models.items():
            metrics = data.get("metrics") if isinstance(data, dict) else None
            if not isinstance(metrics, dict) or metrics.get("r2_score") is None:
                continue
            evaluation[name] = metrics

        if not evaluation:
            return {
                "symbol": symbol,
                "evaluation": None,
                "best_model": None,
                "ensemble_r2": None,
                "has_evaluation": False,
                "message": "Model evaluation has not been performed",
            }

        best_model = max(
            evaluation,
            key=lambda name: float(evaluation[name]["r2_score"]),
        )
        best_metrics = evaluation[best_model]
        best_r2 = float(best_metrics["r2_score"])

        return {
            "symbol": symbol,
            "evaluation": evaluation,
            "best_model": best_model,
            "best_model_label": self._model_label(best_model),
            "best_model_metrics": best_metrics,
            "best_r2_score": round(best_r2, 4),
            "r2_percentage": round(best_r2 * 100, 2),
            "ensemble_r2": round(
                float(np.mean([float(v["r2_score"]) for v in evaluation.values()])),
                4,
            ),
            "evaluated_at": metadata.get("trained_at"),
            "period": metadata.get("period"),
            "training_samples": metadata.get("training_samples"),
            "testing_samples": metadata.get("testing_samples"),
            "split_method": metadata.get("split_method", "unknown"),
            "evaluation_source": "held_out_test_set",
            "has_evaluation": True,
        }

    def get_evaluation_summary(self) -> dict:
        evaluations = []
        for symbol in model_manager.list_evaluated_symbols():
            result = self.get_evaluation(symbol)
            if result.get("has_evaluation"):
                evaluations.append(result)

        if not evaluations:
            return {
                "has_evaluation": False,
                "best_model": None,
                "algorithms": {},
                "evaluated_symbols": [],
                "evaluated_companies": 0,
                "evaluated_at": None,
                "evaluation_source": "held_out_test_set",
                "message": "Model evaluation has not been performed",
            }

        algorithm_scores = {}
        algorithm_metrics = {}

        for result in evaluations:
            for name, metrics in result["evaluation"].items():
                r2_score = metrics.get("r2_score")
                if r2_score is None:
                    continue

                algorithm_scores.setdefault(name, []).append(float(r2_score))
                metric_values = algorithm_metrics.setdefault(
                    name,
                    {"mae": [], "mse": [], "rmse": [], "mape": []},
                )

                for metric_name in metric_values:
                    value = metrics.get(metric_name)
                    if value is not None:
                        metric_values[metric_name].append(float(value))

        algorithms = {}
        for name, scores in algorithm_scores.items():
            average_r2 = round(float(np.mean(scores)), 4)
            averaged_metrics = {
                metric_name: round(float(np.mean(values)), 4)
                for metric_name, values in algorithm_metrics[name].items()
                if values
            }
            averaged_metrics["r2_score"] = average_r2

            algorithms[name] = {
                "algorithm": name,
                "name": name,
                "label": self._model_label(name),
                "average_r2": average_r2,
                "avgR2": average_r2,
                "r2_score": average_r2,
                "r2_percentage": round(average_r2 * 100, 2),
                "evaluated_companies": len(scores),
                "metrics": averaged_metrics,
            }

        best_name = max(
            algorithms,
            key=lambda name: algorithms[name]["average_r2"],
        )
        best_model = algorithms[best_name]
        evaluated_at = max(
            (result["evaluated_at"] for result in evaluations if result.get("evaluated_at")),
            default=None,
        )
        split_methods = {
            result.get("split_method") for result in evaluations if result.get("split_method")
        }

        return {
            "has_evaluation": True,
            "best_model": best_model,
            "algorithms": algorithms,
            "evaluated_symbols": [result["symbol"] for result in evaluations],
            "evaluated_companies": len(evaluations),
            "evaluated_at": evaluated_at,
            "evaluation_source": "held_out_test_set",
            "split_method": (
                split_methods.pop() if len(split_methods) == 1 else "mixed"
            ) if split_methods else "unknown",
        }


prediction_service = PredictionService()
