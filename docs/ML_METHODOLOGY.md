# ML Methodology

This document describes the models, features, targets, and training procedures
used by AI_SMP.

## 1. Scope and universe

- Asset class: Indian Metal & Mining equities listed on NSE.
- Data source: Yahoo Finance daily OHLCV through `yfinance`.
- Default training history: `1y`.
- Prediction horizon: the next trading session's close.

The platform uses technical indicators only. It does not use fundamentals, news,
order-book data, or alternative data.

## 2. Data preparation

`data_service.fetch_stock_data()`:

1. Validates the symbol against a conservative pattern that permits normal
   tickers, indices, and currency pairs while rejecting path traversal,
   whitespace, and separators.
2. Fetches daily history for the requested period.
3. Requires `Date`, `Open`, `High`, `Low`, `Close`, and `Volume`.
4. Converts dates to timezone-naive timestamps, sorts ascending, and drops
   duplicate dates.

`data_service.clean_data()`:

- drops rows missing any required OHLCV field;
- removes duplicate dates;
- removes zero-volume sessions;
- raises if no valid rows remain.

No forward filling is used for prices or volume. Missing indicator values are
dropped after feature construction.

## 3. Features

The feature set is identical for all five models and is ordered deterministically
so training and inference use the same schema:

| Feature | Definition |
|---------|------------|
| `Open`, `High`, `Low`, `Close`, `Volume` | Raw session values |
| `SMA_10`, `SMA_20`, `SMA_50` | Simple moving averages of `Close` |
| `RSI_14` | `100 - 100 / (1 + average gain / average loss)` over 14 sessions |
| `MACD` | 12-period EMA minus 26-period EMA of `Close` |
| `Signal_Line` | 9-period EMA of `MACD` |
| `Bollinger_Upper` | 20-period SMA + 2 × 20-period rolling standard deviation |
| `Bollinger_Lower` | 20-period SMA − 2 × 20-period rolling standard deviation |
| `Price_Change` | `Close.pct_change()` |
| `Volume_Change` | `Volume.pct_change()` |
| `High_Low_Range` | `(High - Low) / Close` |

All indicators are backward-looking and causal. The longest warm-up window is 50
sessions.

### 3.1 Training transform

`feature_engineering.transform(df)`:

1. Builds the 16 features.
2. Adds `Next_Day_Close = Close.shift(-1)`.
3. Drops rows with any missing feature or target.

The final row is dropped because its next-day target is unknown. This keeps each
feature row aligned with the value it is supposed to predict.

### 3.2 Inference transform

`feature_engineering.transform_features(df)`:

1. Builds the same 16 features.
2. Does **not** create a target and does **not** drop the latest row.
3. Validates that the latest session's full feature vector is finite.
4. If the latest row is invalid, raises instead of silently falling back to an
   older session.

This distinction keeps the feature vector and `current_price` aligned with the
same retained session.

## 4. Models

Five regressors are wrapped in small classes:

| Model | Library | Configuration |
|-------|---------|---------------|
| Linear Regression | scikit-learn | Ordinary least squares, default parameters |
| Decision Tree | scikit-learn | `max_depth=10`, `random_state=42` |
| Random Forest | scikit-learn | `n_estimators=100`, `max_depth=15`, `random_state=42`, `n_jobs=-1` |
| Support Vector Regression | scikit-learn | RBF kernel, `C=100`, `gamma="scale"`, `epsilon=0.1`, `StandardScaler` |
| XGBoost | xgboost | `n_estimators=100`, `max_depth=6`, `learning_rate=0.1`, `random_state=42`, `verbosity=0` |

SVR is the only model that requires scaling. Its `StandardScaler` is fitted on
the training rows only and saved separately as `svr_scaler.pkl`.

## 5. Ensemble

The ensemble is a fixed equal-weight arithmetic mean of the five model
predictions. Weights are not learned from validation data. If any component is
unavailable, prediction reports the available component predictions and computes
the ensemble only from finite values; if none are available, it returns
`predicted_price = null` and `signal = "N/A"` rather than fabricating a price.

## 6. Training pipeline

```text
yfinance -> clean -> 16 features + Next_Day_Close -> chronological 80/20 split
         -> fit five models on the earlier 80% -> evaluate on the later 20%
         -> save models, scaler, metrics, and evaluation data in saved_models/
```

- Split method: chronological, not shuffled.
- Train fraction: 80%, test fraction: 20% (`TRAIN_TEST_SPLIT = 0.2`).
- Random state: 42.
- The test set is not used to fit the models.
- Metrics are MAE, MSE, RMSE, R², and MAPE.
- The production signal uses a ±1% threshold around the ensemble prediction:
  BUY above +1%, SELL below −1%, otherwise HOLD.

## 7. Limitations

- The model class is small and uses only technical indicators.
- A single historical path cannot establish a stable edge.
- Hyperparameters are fixed; no systematic tuning is performed.
- `yfinance` data can be revised.
- Market-impact, borrow, taxes, and corporate-action effects are not modelled.
- Results are sensitive to the training window and symbol universe.
- Model outputs are estimates, not predictions of guaranteed future returns.
