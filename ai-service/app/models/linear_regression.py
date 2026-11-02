import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class LinearRegressionModel:
    def __init__(self):
        self.model = LinearRegression()
        self.name = "linear_regression"

    def train(self, X_train: np.ndarray, y_train: np.ndarray):
        self.model.fit(X_train, y_train)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.model.predict(X)

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
