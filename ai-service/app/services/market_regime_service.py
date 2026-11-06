"""Descriptive market-regime classification for a single stock.

The regime is deliberately simple and deterministic: it compares the latest
close with the 50- and 200-session simple moving averages and checks
60-session momentum. It describes past prices; it is not a forecast.
"""

from typing import Any, Dict, Optional

import pandas as pd


BULL = "bull"
BEAR = "bear"
NEUTRAL = "neutral"

LABELS = {
    BULL: "Bullish",
    BEAR: "Bearish",
    NEUTRAL: "Neutral",
}

MIN_HISTORY = 200


class MarketRegimeService:
    """Classify a price history as a bull, bear, or neutral regime."""

    def classify(self, data: pd.DataFrame, symbol: str) -> Dict[str, Any]:
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Stock data is required for market-regime analysis")
        if "Close" not in data.columns:
            raise ValueError("Stock data is missing the Close column")

        closes = pd.to_numeric(data["Close"], errors="coerce").dropna()
        if closes.empty:
            raise ValueError("Stock data has no valid close prices")

        data_points = int(len(closes))
        latest_close = float(closes.iloc[-1])
        as_of = self._as_of(data)

        if data_points < MIN_HISTORY:
            return self._result(
                symbol=symbol,
                regime=NEUTRAL,
                reason=(
                    f"Insufficient history for a 200-session regime: "
                    f"{data_points} valid sessions."
                ),
                as_of=as_of,
                data_points=data_points,
                latest_close=latest_close,
            )

        sma_50 = float(closes.rolling(window=50).mean().iloc[-1])
        sma_200 = float(closes.rolling(window=200).mean().iloc[-1])
        return_20d = self._return(closes, 20)
        return_60d = self._return(closes, 60)
        ma_gap_pct = self._pct_change(sma_50, sma_200)
        distance_from_sma_200_pct = self._pct_change(latest_close, sma_200)

        if latest_close > sma_50 > sma_200 and return_60d > 0:
            regime = BULL
            reason = (
                "Price is above the 50-session average, the 50-session average "
                "is above the 200-session average, and 60-session momentum is positive."
            )
        elif latest_close < sma_50 < sma_200 and return_60d < 0:
            regime = BEAR
            reason = (
                "Price is below the 50-session average, the 50-session average "
                "is below the 200-session average, and 60-session momentum is negative."
            )
        else:
            regime = NEUTRAL
            reason = (
                "The 50/200-session trend and 60-session momentum do not agree "
                "on a bull or bear classification."
            )

        return self._result(
            symbol=symbol,
            regime=regime,
            reason=reason,
            as_of=as_of,
            data_points=data_points,
            latest_close=latest_close,
            sma_50=sma_50,
            sma_200=sma_200,
            ma_gap_pct=ma_gap_pct,
            return_20d_pct=return_20d,
            return_60d_pct=return_60d,
            distance_from_sma_200_pct=distance_from_sma_200_pct,
        )

    @staticmethod
    def _as_of(data: pd.DataFrame) -> Optional[str]:
        if "Date" not in data.columns:
            return None
        valid_close = pd.to_numeric(data["Close"], errors="coerce").notna()
        dates = data.loc[valid_close, "Date"]
        if dates.empty:
            return None
        timestamp = pd.to_datetime(dates.iloc[-1], errors="coerce")
        if pd.isna(timestamp):
            return None
        return timestamp.date().isoformat()

    @staticmethod
    def _return(closes: pd.Series, sessions: int) -> float:
        if len(closes) <= sessions:
            return 0.0
        previous = float(closes.iloc[-(sessions + 1)])
        if previous == 0:
            return 0.0
        return ((float(closes.iloc[-1]) / previous) - 1.0) * 100.0

    @staticmethod
    def _pct_change(value: float, reference: float) -> float:
        if reference == 0:
            return 0.0
        return ((value / reference) - 1.0) * 100.0

    @staticmethod
    def _result(
        symbol: str,
        regime: str,
        reason: str,
        as_of: Optional[str],
        data_points: int,
        latest_close: float,
        sma_50: Optional[float] = None,
        sma_200: Optional[float] = None,
        ma_gap_pct: Optional[float] = None,
        return_20d_pct: Optional[float] = None,
        return_60d_pct: Optional[float] = None,
        distance_from_sma_200_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        def rounded(value: Optional[float]) -> Optional[float]:
            return None if value is None else round(float(value), 4)

        return {
            "symbol": symbol,
            "regime": regime,
            "label": LABELS[regime],
            "reason": reason,
            "as_of": as_of,
            "data_points": data_points,
            "metrics": {
                "latest_close": rounded(latest_close),
                "sma_50": rounded(sma_50),
                "sma_200": rounded(sma_200),
                "ma_gap_pct": rounded(ma_gap_pct),
                "return_20d_pct": rounded(return_20d_pct),
                "return_60d_pct": rounded(return_60d_pct),
                "distance_from_sma_200_pct": rounded(distance_from_sma_200_pct),
            },
            "method": (
                "Latest close versus 50/200-session simple moving averages, "
                "plus 60-session price momentum."
            ),
            "source": "yfinance historical daily closes",
            "disclaimer": (
                "Descriptive classification of historical prices; not a forecast "
                "or investment advice."
            ),
        }


market_regime_service = MarketRegimeService()
