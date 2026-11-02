import pandas as pd
import numpy as np


class FeatureEngineering:
    def __init__(self):
        pass

    def add_sma(self, df: pd.DataFrame, periods: list = [10, 20, 50]) -> pd.DataFrame:
        for period in periods:
            df[f"SMA_{period}"] = df["Close"].rolling(window=period).mean()
        return df

    def add_rsi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        delta = df["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df[f"RSI_{period}"] = 100 - (100 / (1 + rs))
        return df

    def add_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        ema_12 = df["Close"].ewm(span=12, adjust=False).mean()
        ema_26 = df["Close"].ewm(span=26, adjust=False).mean()
        df["MACD"] = ema_12 - ema_26
        df["Signal_Line"] = df["MACD"].ewm(span=9, adjust=False).mean()
        return df

    def add_bollinger_bands(self, df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        sma = df["Close"].rolling(window=period).mean()
        std = df["Close"].rolling(window=period).std()
        df["Bollinger_Upper"] = sma + (2 * std)
        df["Bollinger_Lower"] = sma - (2 * std)
        return df

    def add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df["Price_Change"] = df["Close"].pct_change()
        df["Volume_Change"] = df["Volume"].pct_change()
        df["High_Low_Range"] = (df["High"] - df["Low"]) / df["Close"]
        return df

    def add_target(self, df: pd.DataFrame) -> pd.DataFrame:
        df["Next_Day_Close"] = df["Close"].shift(-1)
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = self.add_sma(df)
        df = self.add_rsi(df)
        df = self.add_macd(df)
        df = self.add_bollinger_bands(df)
        df = self.add_volume_features(df)
        df = self.add_target(df)
        df = df.dropna().reset_index(drop=True)
        return df

    def get_feature_columns(self) -> list:
        return [
            "Open", "High", "Low", "Close", "Volume",
            "SMA_10", "SMA_20", "SMA_50",
            "RSI_14",
            "MACD", "Signal_Line",
            "Bollinger_Upper", "Bollinger_Lower",
            "Price_Change", "Volume_Change", "High_Low_Range",
        ]


feature_engineering = FeatureEngineering()
