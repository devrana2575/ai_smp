import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.services.feature_engineering import feature_engineering
from app.services.prediction_service import prediction_service


def sample_stock_data(rows: int = 90) -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=rows)
    close = 100 + np.linspace(0, 50, rows) + np.sin(np.arange(rows) / 3) * 2

    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.full(rows, 1_000_000),
        }
    )


class FeatureEngineeringTests(unittest.TestCase):
    def test_training_transform_drops_the_unlabelled_latest_row(self):
        df = sample_stock_data()
        featured = feature_engineering.transform(df)

        self.assertEqual(featured["Date"].iloc[-1], df["Date"].iloc[-2])
        self.assertEqual(featured["Next_Day_Close"].iloc[-1], df["Close"].iloc[-1])

    def test_inference_transform_keeps_the_latest_row(self):
        df = sample_stock_data()
        featured = feature_engineering.transform(df, include_target=False)

        self.assertNotIn("Next_Day_Close", featured.columns)
        self.assertEqual(featured["Date"].iloc[-1], df["Date"].iloc[-1])
        self.assertAlmostEqual(featured["Close"].iloc[-1], df["Close"].iloc[-1])


class PredictionAlignmentTests(unittest.TestCase):
    def test_predict_uses_the_latest_feature_row(self):
        df = sample_stock_data()
        received = {}

        class RecordingModel:
            def predict(self, X):
                received["X"] = np.array(X, copy=True)
                return np.array([210.0])

        with patch(
            "app.services.prediction_service.data_service.fetch_stock_data",
            return_value=df,
        ), patch(
            "app.services.prediction_service.data_service.clean_data",
            side_effect=lambda frame: frame.reset_index(drop=True),
        ), patch(
            "app.services.prediction_service.model_manager.load_model",
            return_value=RecordingModel(),
        ), patch(
            "app.services.prediction_service.model_manager.load_scaler",
            return_value=None,
        ):
            result = prediction_service.predict("TEST.NS")

        close_index = feature_engineering.get_feature_columns().index("Close")
        self.assertAlmostEqual(received["X"][0][close_index], df["Close"].iloc[-1])
        self.assertEqual(result["current_price"], round(float(df["Close"].iloc[-1]), 2))
        self.assertEqual(result["predicted_price"], 210.0)


if __name__ == "__main__":
    unittest.main()
