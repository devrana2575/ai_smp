import numpy as np
import pandas as pd
import pytest

from app.services.data_service import data_service, validate_symbol


@pytest.mark.parametrize(
    "symbol",
    ["TATASTEEL.NS", "M&M.NS", "BAJAJ-AUTO.NS", "^NSEI", "BTC-USD", "EURUSD=X"],
)
def test_validate_symbol_accepts_supported_tickers(symbol):
    assert validate_symbol(symbol) == symbol


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        "   ",
        "..",
        "../TATASTEEL.NS",
        "TATA/STEEL",
        "TATA\\STEEL",
        "TATA STEEL",
        "TATA?STEEL",
    ],
)
def test_validate_symbol_rejects_invalid_tickers(symbol):
    with pytest.raises(ValueError, match="Invalid stock symbol"):
        validate_symbol(symbol)


def test_validate_symbol_rejects_non_string_values():
    with pytest.raises(ValueError, match="must be a string"):
        validate_symbol(None)


def test_fetch_stock_data_rejects_invalid_symbol_before_network():
    with pytest.raises(ValueError, match="Invalid stock symbol"):
        data_service.fetch_stock_data("../TATASTEEL.NS")


def test_clean_data_drops_rows_with_missing_values(stock_data_factory):
    df = stock_data_factory(10)
    df.loc[2, "Close"] = np.nan

    cleaned = data_service.clean_data(df)

    assert len(cleaned) == 9
    assert cleaned["Date"].is_unique
    assert cleaned["Volume"].gt(0).all()
    assert not cleaned[["Open", "High", "Low", "Close", "Volume"]].isna().any().any()


def test_clean_data_rejects_empty_result(stock_data_factory):
    df = stock_data_factory(10)
    df["Volume"] = 0

    with pytest.raises(ValueError, match="No valid stock rows remain"):
        data_service.clean_data(df)


def test_clean_data_rejects_missing_required_columns(stock_data_factory):
    df = stock_data_factory(10).drop(columns=["Close"])

    with pytest.raises(ValueError, match="missing required columns"):
        data_service.clean_data(df)


def test_clean_data_rejects_empty_input():
    with pytest.raises(ValueError, match="No stock data available"):
        data_service.clean_data(pd.DataFrame())
