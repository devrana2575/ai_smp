import numpy as np
import pytest
from sklearn.preprocessing import StandardScaler

import app.services.prediction_service as prediction_service_module
from app.services.feature_engineering import feature_engineering
from app.services.prediction_service import prediction_service


EXPECTED_FEATURE_COLUMNS = [
    "Open", "High", "Low", "Close", "Volume",
    "SMA_10", "SMA_20", "SMA_50",
    "RSI_14",
    "MACD", "Signal_Line",
    "Bollinger_Upper", "Bollinger_Lower",
    "Price_Change", "Volume_Change", "High_Low_Range",
]


def latest_feature_vector(df) -> np.ndarray:
    featured = feature_engineering.transform_features(df)
    return (
        featured.iloc[-1][feature_engineering.get_feature_columns()]
        .to_numpy(dtype=float)
    )


class TestFeatureEngineering:
    def test_feature_only_transform_retains_latest_valid_row(
        self, stock_data_factory
    ):
        df = stock_data_factory(90)
        featured = feature_engineering.transform_features(df)

        assert "Next_Day_Close" not in featured.columns
        assert featured["Date"].iloc[-1] == df["Date"].iloc[-1]
        assert featured["Close"].iloc[-1] == pytest.approx(df["Close"].iloc[-1])
        assert len(featured) == len(df) - feature_engineering.MIN_HISTORY_ROWS + 1
        assert not featured[feature_engineering.get_feature_columns()].isna().any().any()

    def test_feature_only_transform_keeps_minimum_history_row(
        self, stock_data_factory
    ):
        df = stock_data_factory(feature_engineering.MIN_HISTORY_ROWS)
        featured = feature_engineering.transform_features(df)

        assert len(featured) == 1
        assert featured["Date"].iloc[-1] == df["Date"].iloc[-1]
        assert featured["Close"].iloc[-1] == pytest.approx(df["Close"].iloc[-1])

    def test_feature_only_transform_removes_an_existing_target_column(
        self, stock_data_factory
    ):
        df = stock_data_factory(90)
        df["Next_Day_Close"] = df["Close"].shift(-1)

        featured = feature_engineering.transform_features(df)

        assert "Next_Day_Close" not in featured.columns
        assert featured["Date"].iloc[-1] == df["Date"].iloc[-1]

    def test_include_target_false_alias_matches_feature_only_transform(
        self, stock_data_factory
    ):
        df = stock_data_factory(90)

        assert feature_engineering.transform(df, include_target=False).equals(
            feature_engineering.transform_features(df)
        )

    def test_training_transform_keeps_target_aligned(self, stock_data_factory):
        df = stock_data_factory(90)
        featured = feature_engineering.transform(df)

        assert "Next_Day_Close" in featured.columns
        assert featured["Date"].iloc[-1] == df["Date"].iloc[-2]
        assert featured["Close"].iloc[-1] == pytest.approx(df["Close"].iloc[-2])
        assert featured["Next_Day_Close"].iloc[-1] == pytest.approx(
            df["Close"].iloc[-1]
        )

        # Each target is the next retained row's close, so features at t are
        # never paired with a close at or before t.
        np.testing.assert_allclose(
            featured["Next_Day_Close"].iloc[:-1].to_numpy(),
            featured["Close"].iloc[1:].to_numpy(),
        )
        assert "Next_Day_Close" not in feature_engineering.get_feature_columns()

    def test_feature_column_order_is_consistent(self, stock_data_factory):
        df = stock_data_factory(90)
        expected = EXPECTED_FEATURE_COLUMNS

        assert feature_engineering.get_feature_columns() == expected
        assert len(expected) == 16

        training = feature_engineering.transform(df)
        inference = feature_engineering.transform_features(df)

        assert training[expected].columns.tolist() == expected
        assert inference[expected].columns.tolist() == expected

    def test_transform_features_rejects_insufficient_history(
        self, stock_data_factory
    ):
        df = stock_data_factory(feature_engineering.MIN_HISTORY_ROWS - 1)

        with pytest.raises(ValueError, match="Not enough historical data"):
            feature_engineering.transform_features(df)

    def test_transform_features_rejects_missing_latest_feature_values(
        self, stock_data_factory
    ):
        df = stock_data_factory(90)
        df.loc[df.index[-1], "Close"] = np.nan

        with pytest.raises(ValueError, match="latest trading day"):
            feature_engineering.transform_features(df)


class TestPredictionInference:
    def test_predict_uses_latest_trading_day_features_and_price(
        self, stock_data_factory, monkeypatch
    ):
        df = stock_data_factory(90)
        expected_vector = latest_feature_vector(df)

        class RecordingModel:
            def __init__(self):
                self.received = None

            def predict(self, X):
                self.received = np.array(X, copy=True)
                return np.array([210.0])

        recorder = RecordingModel()

        def fake_load_model(symbol, model_name):
            return recorder if model_name == "linear_regression" else None

        monkeypatch.setattr(
            prediction_service_module.data_service,
            "fetch_stock_data",
            lambda symbol, period: df.copy(),
        )
        monkeypatch.setattr(
            prediction_service_module.model_manager,
            "load_model",
            fake_load_model,
        )

        result = prediction_service.predict("TEST.NS")

        assert recorder.received is not None
        assert recorder.received.shape == (1, len(expected_vector))
        np.testing.assert_allclose(recorder.received[0], expected_vector)
        assert result["current_price"] == round(float(df["Close"].iloc[-1]), 2)
        assert result["models"]["linear_regression"]["prediction"] == 210.0
        assert result["predicted_price"] == 210.0

    def test_predict_uses_saved_scaler_for_svr(
        self, stock_data_factory, monkeypatch
    ):
        df = stock_data_factory(120)
        feature_cols = feature_engineering.get_feature_columns()
        training = feature_engineering.transform(df)
        scaler = StandardScaler().fit(
            training[feature_cols].to_numpy(dtype=float)
        )

        expected_vector = latest_feature_vector(df).reshape(1, -1)
        expected_scaled = scaler.transform(expected_vector)

        class RecordingSvrEstimator:
            def __init__(self):
                self.received = None

            def predict(self, X):
                self.received = np.array(X, copy=True)
                return np.array([321.0])

        estimator = RecordingSvrEstimator()

        def fake_load_model(symbol, model_name):
            return estimator if model_name == "svr" else None

        def fake_load_scaler(symbol, model_name):
            return scaler if model_name == "svr" else None

        monkeypatch.setattr(
            prediction_service_module.data_service,
            "fetch_stock_data",
            lambda symbol, period: df.copy(),
        )
        monkeypatch.setattr(
            prediction_service_module.model_manager,
            "load_model",
            fake_load_model,
        )
        monkeypatch.setattr(
            prediction_service_module.model_manager,
            "load_scaler",
            fake_load_scaler,
        )

        result = prediction_service.predict("TEST.NS")

        assert estimator.received is not None
        np.testing.assert_allclose(estimator.received, expected_scaled)
        assert not np.allclose(estimator.received, expected_vector)
        assert result["models"]["svr"]["prediction"] == 321.0
        assert result["predicted_price"] == 321.0

    def test_predict_does_not_fabricate_price_without_trained_models(
        self, stock_data_factory, monkeypatch
    ):
        df = stock_data_factory(90)

        monkeypatch.setattr(
            prediction_service_module.data_service,
            "fetch_stock_data",
            lambda symbol, period: df.copy(),
        )
        monkeypatch.setattr(
            prediction_service_module.model_manager,
            "load_model",
            lambda symbol, model_name: None,
        )

        result = prediction_service.predict("TEST.NS")

        assert result["current_price"] == round(float(df["Close"].iloc[-1]), 2)
        assert result["predicted_price"] is None
        assert result["ensemble_prediction"] is None
        assert result["signal"] == "N/A"
        assert set(result["models"]) == set(prediction_service.models)
        for model_result in result["models"].values():
            assert model_result == {
                "prediction": None,
                "error": "Model not trained",
            }

    def test_predict_marks_svr_unavailable_when_scaler_is_missing(
        self, stock_data_factory, monkeypatch
    ):
        df = stock_data_factory(90)

        class DummyEstimator:
            def predict(self, X):
                return np.array([999.0])

        monkeypatch.setattr(
            prediction_service_module.data_service,
            "fetch_stock_data",
            lambda symbol, period: df.copy(),
        )
        monkeypatch.setattr(
            prediction_service_module.model_manager,
            "load_model",
            lambda symbol, model_name: (
                DummyEstimator() if model_name == "svr" else None
            ),
        )
        monkeypatch.setattr(
            prediction_service_module.model_manager,
            "load_scaler",
            lambda symbol, model_name: None,
        )

        result = prediction_service.predict("TEST.NS")

        assert result["models"]["svr"] == {
            "prediction": None,
            "error": "Model scaler not found",
        }
        assert result["predicted_price"] is None
        assert result["signal"] == "N/A"

    @pytest.mark.parametrize(
        "symbol",
        ["../TATASTEEL.NS", "TATA/STEEL", "TATA STEEL", ""],
    )
    def test_predict_rejects_invalid_symbols(self, symbol):
        with pytest.raises(ValueError, match="Invalid stock symbol"):
            prediction_service.predict(symbol)

    def test_predict_rejects_insufficient_history(
        self, stock_data_factory, monkeypatch
    ):
        df = stock_data_factory(feature_engineering.MIN_HISTORY_ROWS - 1)

        monkeypatch.setattr(
            prediction_service_module.data_service,
            "fetch_stock_data",
            lambda symbol, period: df.copy(),
        )

        with pytest.raises(ValueError, match="Not enough historical data"):
            prediction_service.predict("TEST.NS")
