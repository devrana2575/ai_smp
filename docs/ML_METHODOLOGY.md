# ML Methodology

This document describes the models, features, targets, training procedures, and
leakage controls used by AI_SMP 2.0. It covers both the preserved legacy
production path and the additive research path.

## 1. Scope and universe

- Asset class: Indian Metal & Mining equities listed on NSE.
- Evaluated symbols in the live reports:
  `COALINDIA.NS`, `HINDALCO.NS`, `HINDZINC.NS`, `JINDALSTEL.NS`,
  `JSWSTEEL.NS`, `TATASTEEL.NS`.
- Data source: Yahoo Finance daily OHLCV through `yfinance`.
- Legacy training history: `1y` by default.
- Research evaluation history: `2y` by default.
- Prediction horizon: the next trading session's close.

The platform is a research and education system. It does not use fundamentals,
news, order-book data, or alternative data.

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
feature row aligned with the return it is supposed to predict.

### 3.2 Inference transform

`feature_engineering.transform_features(df)`:

1. Builds the same 16 features.
2. Does **not** create a target and does **not** drop the latest row.
3. Validates that the latest session's full feature vector is finite.
4. If the latest row is invalid, raises instead of silently falling back to an
   older session.

This distinction fixes the historical one-session feature/price misalignment.
The legacy prediction path reads `current_price` from the same retained row as
the feature vector.

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
the training rows only and saved separately as `svr_scaler.pkl` in the legacy
artifact layout and as `svr_scaler.pkl` in each registry version.

## 5. Ensemble

The ensemble is a fixed equal-weight arithmetic mean of the five model
predictions. Weights are not learned from validation or holdout data. If any
component is unavailable, the legacy prediction reports the available component
predictions and computes the ensemble only from finite values; if none are
available, it returns `predicted_price = null` and `signal = "N/A"` rather than
fabricating a price.

## 6. Legacy training pipeline

```text
yfinance -> clean -> 16 features + Next_Day_Close -> chronological 80/20 split
         -> fit five models on the earlier 80% -> evaluate on the later 20%
         -> save models, scaler, metrics, and evaluation data in saved_models/
```

- Split method: chronological, not shuffled.
- Train fraction: 80%, test fraction: 20% (`TRAIN_TEST_SPLIT = 0.2`).
- Random state: 42.
- The test set is not used to fit the models.
- Legacy metrics are MAE, MSE, RMSE, R², and MAPE.
- The production signal uses a ±1% threshold around the ensemble prediction:
  BUY above +1%, SELL below −1%, otherwise HOLD.
- Training and prediction endpoints are unchanged by the research layer.

## 7. Walk-forward research methodology

### 7.1 Dataset

For a requested symbol and period, the research service fetches and cleans the
data, builds the causal features, and records both:

- the **feature date** (the session whose close is known), and
- the **target date** (the next session whose close is predicted).

It also records the actual next-session open for backtesting. A SHA-256
fingerprint of the cleaned OHLCV data is stored in the report so a run can be
checked for data drift.

### 7.2 Development/holdout split

- The most recent `holdout_fraction` of feature rows (default 20%) is reserved
  as the final holdout.
- The split is computed before model selection.
- The holdout is never used for feature choice, hyperparameter tuning, model
  selection, or ensemble weights.
- A minimum number of holdout rows is enforced (default 10).

### 7.3 Expanding folds

- The development portion is divided into chronological expanding-window folds.
- Fold 1 trains on the initial development prefix and validates on the next
  block; later folds extend the training prefix.
- No shuffling is used anywhere.
- Each training row's target date must be strictly earlier than the first
  validation target date. This is checked, not assumed.
- Each fold fits fresh model instances, including a fresh SVR scaler on that
  fold's training rows.

### 7.4 Model selection

Candidates are ranked on **pooled development walk-forward validation metrics**:

1. RMSE (primary; lower is better),
2. MAE (tie-break),
3. directional accuracy (tie-break; higher is better).

R² is reported but is not the primary selection criterion. The naive-persistence
baseline is included in the all-candidate ranking but excluded from the
deployable-model selection set (the five ML models plus the equal-weight
ensemble). Selection is locked before the holdout is evaluated.

### 7.5 Final holdout

After selection is recorded, all candidates are refit on the development data
that precedes the holdout and evaluated once on the untouched holdout. The
report includes both the selected model and the best holdout model for
transparency; the latter does not change the selection.

## 8. Return-target experiment (Phase 2.1)

The same data, features, folds, and holdout boundaries are reused for three
target formulations:

| Family | Training target | Price reconstruction |
|--------|-----------------|----------------------|
| Absolute price | `Next_Day_Close` | predicted price used directly |
| Simple return | `Next_Day_Close / Close - 1` | `Close × (1 + predicted_return)` |
| Log return | `log(Next_Day_Close / Close)` | `Close × exp(predicted_log_return)` |

The zero-return persistence baseline predicts no movement in every family:

- absolute-price family: predict the current close;
- return families: predict zero return and reconstruct the current close.

Metrics are computed both on the native return scale and on reconstructed
prices. This makes it possible to compare families that optimize different
targets without hiding price-level error.

## 9. Registered-model candidate training

The model registry trains a candidate on a chronological split:

- history period: request value or `TRAINING_PERIOD` (default `1y`);
- split: first 80% for fitting, last 20% for validation;
- all five models are fitted;
- validation metrics include MAE, RMSE, R², sMAPE, directional metrics,
  normalized errors, and a naive-persistence comparison;
- artifacts are written under
  `model_registry/artifacts/{SYMBOL}/{version}/`;
- `saved_models/` is never modified;
- a failed candidate is removed from the registry and its artifact directory is
  discarded;
- activation requires explicit approval and artifact compatibility checks.

The candidate is not production-active until an administrator approves and
activates it.

## 10. Leakage controls summary

- No random shuffling in training, evaluation, or backtesting.
- No future values in feature construction; all indicators use current/past rows.
- Target dates explicitly aligned to feature dates.
- Training target dates must precede validation target dates.
- Final holdout isolated before selection.
- Per-fold scaler fitting.
- Return predictions reconstructed from the current close, not from the future.
- Backtest execution at the next open, not the signal-day close.
- Zero-return baseline treated as abstention, not as a directional observation.

## 11. Limitations

- The model class is small and uses only technical indicators.
- A single historical path cannot establish a stable edge.
- Hyperparameters are fixed; no systematic tuning is performed on the holdout.
- `yfinance` data can be revised; reports include a fingerprint but not a full
  vendor audit trail.
- No transaction-level market impact, borrow, taxes, or corporate-action model.
- Results are sensitive to the evaluation window and symbol universe.
- The live reports in this repository are historical simulations, not
  predictions of future returns.
