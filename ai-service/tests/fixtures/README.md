# Synthetic test fixtures

`synthetic_ohlcv.csv` is **not market data**. It is a deterministic, artificial
OHLCV series generated for offline tests and examples. Prices follow a smooth
linear trend plus a sine wave; volume is constant.

The file exists so tests can exercise data cleaning, feature engineering,
walk-forward splitting, and backtest plumbing without calling yfinance or
depending on a live network connection. Any evaluation or backtest report
generated from it must be labelled `synthetic_test_data` and must never be
presented as evidence of real-market performance.
