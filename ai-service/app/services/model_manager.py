import os
import joblib
from app.config import settings


class ModelManager:
    def __init__(self):
        self.base_dir = settings.SAVED_MODELS_DIR

    def get_model_dir(self, symbol: str) -> str:
        model_dir = os.path.join(self.base_dir, symbol.replace(".", "_"))
        os.makedirs(model_dir, exist_ok=True)
        return model_dir

    def save_model(self, symbol: str, model_name: str, model, scaler=None):
        model_dir = self.get_model_dir(symbol)
        model_path = os.path.join(model_dir, f"{model_name}.pkl")
        joblib.dump(model, model_path)

        if scaler is not None:
            scaler_path = os.path.join(model_dir, f"{model_name}_scaler.pkl")
            joblib.dump(scaler, scaler_path)

    def load_model(self, symbol: str, model_name: str):
        model_dir = self.get_model_dir(symbol)
        model_path = os.path.join(model_dir, f"{model_name}.pkl")

        if not os.path.exists(model_path):
            return None

        return joblib.load(model_path)

    def load_scaler(self, symbol: str, model_name: str):
        model_dir = self.get_model_dir(symbol)
        scaler_path = os.path.join(model_dir, f"{model_name}_scaler.pkl")

        if not os.path.exists(scaler_path):
            return None

        return joblib.load(scaler_path)

    def is_trained(self, symbol: str, model_name: str) -> bool:
        model_dir = self.get_model_dir(symbol)
        model_path = os.path.join(model_dir, f"{model_name}.pkl")
        return os.path.exists(model_path)

    def get_all_models_status(self, symbol: str) -> dict:
        model_names = ["linear_regression", "decision_tree", "random_forest", "svr", "xgboost"]
        return {name: self.is_trained(symbol, name) for name in model_names}

    def delete_model(self, symbol: str, model_name: str):
        model_dir = self.get_model_dir(symbol)
        model_path = os.path.join(model_dir, f"{model_name}.pkl")
        scaler_path = os.path.join(model_dir, f"{model_name}_scaler.pkl")

        if os.path.exists(model_path):
            os.remove(model_path)
        if os.path.exists(scaler_path):
            os.remove(scaler_path)

    def save_metrics(self, symbol: str, metrics: dict):
        model_dir = self.get_model_dir(symbol)
        metrics_path = os.path.join(model_dir, "metrics.pkl")
        joblib.dump(metrics, metrics_path)

    def load_metrics(self, symbol: str) -> dict:
        model_dir = self.get_model_dir(symbol)
        metrics_path = os.path.join(model_dir, "metrics.pkl")

        if not os.path.exists(metrics_path):
            return None

        return joblib.load(metrics_path)

    def save_evaluation_data(self, symbol: str, evaluation_data: dict):
        model_dir = self.get_model_dir(symbol)
        data_path = os.path.join(model_dir, "evaluation_data.pkl")
        joblib.dump(evaluation_data, data_path)

    def load_evaluation_data(self, symbol: str) -> dict:
        model_dir = self.get_model_dir(symbol)
        data_path = os.path.join(model_dir, "evaluation_data.pkl")

        if not os.path.exists(data_path):
            return None

        return joblib.load(data_path)

    def list_evaluated_symbols(self) -> list:
        if not os.path.isdir(self.base_dir):
            return []

        symbols = []
        for entry in sorted(os.listdir(self.base_dir)):
            model_dir = os.path.join(self.base_dir, entry)
            if not os.path.isdir(model_dir):
                continue

            metrics_path = os.path.join(model_dir, "metrics.pkl")
            if not os.path.exists(metrics_path):
                continue

            metrics = joblib.load(metrics_path)
            symbol = metrics.get("symbol") if isinstance(metrics, dict) else None

            if not symbol:
                if "_" in entry:
                    base, suffix = entry.rsplit("_", 1)
                    symbol = f"{base}.{suffix}" if suffix in {"NS", "BO"} else entry
                else:
                    symbol = entry

            symbols.append(symbol)

        return symbols


model_manager = ModelManager()
