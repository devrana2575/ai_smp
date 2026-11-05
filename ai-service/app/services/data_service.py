import re

import pandas as pd
import yfinance as yf


REQUIRED_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]

# Supports normal tickers (TATASTEEL.NS, M&M.NS, BTC-USD), indices (^NSEI),
# and currency pairs (EURUSD=X), while rejecting path separators and spaces.
SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9^][A-Za-z0-9.^=&\-]{0,31}$")


def validate_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise ValueError("Stock symbol must be a string")

    normalized = symbol.strip()
    if (
        not normalized
        or ".." in normalized
        or not SYMBOL_PATTERN.fullmatch(normalized)
    ):
        raise ValueError(f"Invalid stock symbol: {symbol!r}")

    return normalized


class DataService:
    def __init__(self):
        pass

    def fetch_stock_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        symbol = validate_symbol(symbol)
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)

        if df.empty:
            raise ValueError(f"No data found for symbol: {symbol}")

        df = df.reset_index()
        missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError(
                f"Stock data for {symbol} is missing required columns: "
                + ", ".join(missing)
            )

        df = df[REQUIRED_COLUMNS]
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        df = df.sort_values("Date").reset_index(drop=True)

        return df

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("No stock data available to clean")

        missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise ValueError(
                "Stock data is missing required columns: " + ", ".join(missing)
            )

        cleaned = df.dropna(subset=REQUIRED_COLUMNS)
        cleaned = cleaned.drop_duplicates(subset=["Date"])
        cleaned = cleaned[cleaned["Volume"] > 0]

        if cleaned.empty:
            raise ValueError(
                "No valid stock rows remain after removing missing values"
            )

        return cleaned.reset_index(drop=True)

    def get_stock_info(self, symbol: str) -> dict:
        symbol = validate_symbol(symbol)
        stock = yf.Ticker(symbol)
        info = stock.info
        return {
            "symbol": symbol,
            "name": info.get("longName", symbol),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "currentPrice": info.get("currentPrice", 0),
            "marketCap": info.get("marketCap", 0),
        }


data_service = DataService()
