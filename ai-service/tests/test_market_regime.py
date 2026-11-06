import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.routes import stock_routes
from app.services.market_regime_service import market_regime_service


SERVICE_TOKEN = "test-internal-service-token-0123456789"
client = TestClient(app, headers={"X-Internal-Service-Token": SERVICE_TOKEN})


def test_uptrend_is_bullish(stock_data_factory):
    data = stock_data_factory(rows=260)

    result = market_regime_service.classify(data, "TEST.NS")

    assert result["regime"] == "bull"
    assert result["label"] == "Bullish"
    assert result["metrics"]["sma_50"] > result["metrics"]["sma_200"]
    assert result["metrics"]["return_60d_pct"] > 0
    assert result["disclaimer"].startswith("Descriptive")


def test_downtrend_is_bearish(stock_data_factory):
    data = stock_data_factory(rows=260)
    data["Close"] = np.linspace(200, 80, len(data))

    result = market_regime_service.classify(data, "TEST.NS")

    assert result["regime"] == "bear"
    assert result["label"] == "Bearish"
    assert result["metrics"]["sma_50"] < result["metrics"]["sma_200"]
    assert result["metrics"]["return_60d_pct"] < 0


def test_flat_prices_are_neutral(stock_data_factory):
    data = stock_data_factory(rows=260)
    data["Close"] = 100.0

    result = market_regime_service.classify(data, "TEST.NS")

    assert result["regime"] == "neutral"
    assert result["label"] == "Neutral"


def test_insufficient_history_is_neutral(stock_data_factory):
    data = stock_data_factory(rows=100)

    result = market_regime_service.classify(data, "TEST.NS")

    assert result["regime"] == "neutral"
    assert result["data_points"] == 100
    assert "Insufficient history" in result["reason"]
    assert result["metrics"]["sma_200"] is None


def test_regime_endpoint_returns_classification(monkeypatch, stock_data_factory):
    data = stock_data_factory(rows=260)
    monkeypatch.setattr(
        stock_routes.data_service,
        "fetch_stock_data",
        lambda symbol, period: data,
    )

    response = client.get("/api/stock-data/TEST.NS/regime")

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "TEST.NS"
    assert payload["regime"] == "bull"
    assert payload["data_points"] == len(data)
    assert payload["metrics"]["sma_200"] is not None
    assert payload["source"] == "yfinance historical daily closes"
