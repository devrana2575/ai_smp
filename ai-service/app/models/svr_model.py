import numpy as np
from sklearn.svm import SVR
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class SVRModel:
    def __init__(self):
        self.model = SVR(kernel="rbf", C=100, gamma="scale", epsilon=0.1)
        self.scaler = StandardScaler()
        self.name = "svr"

    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        X_train_scaled = self.scaler.fit_transform(X_train)
        self.model.fit(X_train_scaled, y_train)

    def predict(self, X: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> dict:
        predictions = self.predict(X_test)
        return self.calculate_metrics(y_test, predictions)

    def calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> dict:
        mae = mean_absolute_error(y_true, y_pred)
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_true, y_pred)

        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100

        return {
            "mae": round(mae, 4),
            "mse": round(mse, 4),
            "rmse": round(rmse, 4),
            "r2_score": round(r2, 4),
            "mape": round(mape, 4),
        }

    def get_scaler(self):
        return self.scaler
