import numpy as np
import pandas as pd


class FeatureEngineering:
    REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

    # Keep this order stable: the same order must be used for training and
    # inference because the saved models were fitted on these columns.
    FEATURE_COLUMNS = (
        "Open", "High", "Low", "Close", "Volume",
        "SMA_10", "SMA_20", "SMA_50",
        "RSI_14",
        "MACD", "Signal_Line",
        "Bollinger_Upper", "Bollinger_Lower",
        "Price_Change", "Volume_Change", "High_Low_Range",
    )

    # The longest rolling window used by the indicators is 50 sessions.
    # Fifty cleaning-complete rows are therefore enough to build one feature
    # vector, but training needs additional rows to create a target and split.
    MIN_HISTORY_ROWS = 50

    def __init__(self):
        pass

    def _validate_input(self, df: pd.DataFrame) -> None:
        if not isinstance(df, pd.DataFrame):
            raise ValueError("Stock data must be a pandas DataFrame")

        missing = [
            column for column in self.REQUIRED_COLUMNS if column not in df.columns
        ]
        if missing:
            raise ValueError(
                "Stock data is missing required columns: " + ", ".join(missing)
            )

        if len(df) < self.MIN_HISTORY_ROWS:
            raise ValueError(
                "Not enough historical data: received "
                f"{len(df)} rows, need at least {self.MIN_HISTORY_ROWS}"
            )

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
        df["Price_Change"] = df["Close"].pct_change(fill_method=None)
        df["Volume_Change"] = df["Volume"].pct_change(fill_method=None)
        df["High_Low_Range"] = (df["High"] - df["Low"]) / df["Close"]
        return df

    def add_target(self, df: pd.DataFrame) -> pd.DataFrame:
        # Training-only target. The last row has no next-day close, so it must
        # never be used as an inference row.
        df["Next_Day_Close"] = df["Close"].shift(-1)
        return df

    def _add_features(self, df: pd.DataFrame) -> pd.DataFrame:
        # Every indicator below is backward-looking: it uses the current row
        # and earlier rows only. No future data is used to build features.
        df = self.add_sma(df)
        df = self.add_rsi(df)
        df = self.add_macd(df)
        df = self.add_bollinger_bands(df)
        df = self.add_volume_features(df)
        return df

    def transform(self, df: pd.DataFrame, include_target: bool = True) -> pd.DataFrame:
        """Build training features and, by default, the next-day target.

        ``include_target=False`` is kept as a compatibility alias for
        :meth:`transform_features`. Training must use ``include_target=True``
        so the target and feature rows stay aligned.
        """
        if not include_target:
            return self.transform_features(df)

        self._validate_input(df)
        df = df.copy()
        df = self._add_features(df)
        df = self.add_target(df)

        # Drop indicator warm-up rows and the final row whose next-day target
        # is unknown. This is correct for training data only.
        df = df.dropna().reset_index(drop=True)
        if df.empty:
            raise ValueError("Not enough historical data to build training rows")
        return df

    def transform_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build inference features without creating or dropping a target.

        Inference must retain the most recent trading day. The training
        transform adds ``Next_Day_Close`` and drops the resulting NaN row,
        which would move inference back by one session. This method computes
        the same indicators but leaves the latest row available.
        """
        self._validate_input(df)

        df = df.copy()
        # If a training frame is accidentally passed here, remove the target
        # before building features so it cannot leak into inference.
        df = df.drop(columns=["Next_Day_Close"], errors="ignore")
        df = self._add_features(df)

        feature_columns = self.get_feature_columns()

        # Validate the latest row before dropping warm-up rows. If the newest
        # session has a missing/invalid feature value, falling back to an older
        # row would silently reintroduce the original feature/price mismatch.
        latest_row = df.iloc[[-1]]
        latest_values = latest_row[feature_columns].to_numpy(dtype=float)
        if not np.all(np.isfinite(latest_values)):
            raise ValueError(
                "The latest trading day's feature vector contains missing or "
                "non-finite values; cannot make an aligned prediction"
            )

        features = df.dropna(subset=feature_columns).reset_index(drop=True)
        if features.empty:
            raise ValueError("No complete feature rows are available")

        if "Date" in df.columns and features["Date"].iloc[-1] != df["Date"].iloc[-1]:
            raise ValueError("The latest trading day's features were not retained")

        return features

    def get_feature_columns(self) -> list:
        return list(self.FEATURE_COLUMNS)


feature_engineering = FeatureEngineering()
