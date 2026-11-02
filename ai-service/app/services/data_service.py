import yfinance as yf
import pandas as pd
from typing import Optional


class DataService:
    def __init__(self):
        pass

    def fetch_stock_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)

        if df.empty:
            raise ValueError(f"No data found for symbol: {symbol}")

        df = df.reset_index()
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]]
        df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
        df = df.sort_values("Date").reset_index(drop=True)

        return df

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.dropna()
        df = df.drop_duplicates(subset=["Date"])
        df = df[df["Volume"] > 0]
        return df.reset_index(drop=True)

    def get_stock_info(self, symbol: str) -> dict:
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
