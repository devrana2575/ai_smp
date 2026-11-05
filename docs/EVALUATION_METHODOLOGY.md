# Evaluation Methodology

This document defines how AI_SMP 2.0 evaluates forecasts. The goal is to produce
leakage-free, reproducible, and honestly reported out-of-sample results. It also
records the actual outcomes of the live reports in this repository.

## 1. Principles

1. **Chronology is preserved.** No random shuffling in training, validation, or
   backtesting.
2. **The final holdout is locked.** It is created before model selection and is
   never used for feature choice, tuning, selection, or ensemble weights.
3. **Every candidate sees the same folds.** Absolute-price, simple-return, and
   log-return experiments use identical dataset construction, folds, and holdout
   boundaries.
4. **Direction is abstention-aware.** A predicted movement of exactly zero is an
   abstention, not a wrong direction.
5. **No fabricated scores.** Metrics that are undefined are reported as `null`,
   not as zero.
6. **R² is not the selection criterion.** RMSE is primary; MAE and directional
   accuracy are tie-breakers.
7. **Results are labeled as simulations.** No metric in this document is a
   profitability guarantee.

## 2. Data and evaluation windows

The live reports used:

- source: Yahoo Finance via `yfinance`;
- period: `2y`;
- six NSE symbols: `COALINDIA.NS`, `HINDALCO.NS`, `HINDZINC.NS`,
  `JINDALSTEL.NS`, `JSWSTEEL.NS`, `TATASTEEL.NS`;
- five expanding walk-forward folds;
- a 20% final holdout (89 rows per symbol; JINDALSTEL has 354 development rows
  because its raw history differs by one session).

Cleaned and feature-row counts:

| Symbol | Clean rows | Feature/target rows | Development rows | Holdout rows | Holdout dates |
|--------|------------|---------------------|------------------|--------------|---------------|
| COALINDIA.NS | 494 | 444 | 355 | 89 | 2026-06-29 → 2026-11-03 |
| HINDALCO.NS | 494 | 444 | 355 | 89 | 2026-06-29 → 2026-11-03 |
| HINDZINC.NS | 494 | 444 | 355 | 89 | 2026-06-29 → 2026-11-03 |
| JINDALSTEL.NS | 493 | 443 | 354 | 89 | 2026-06-25 → 2026-11-02 |
| JSWSTEEL.NS | 494 | 444 | 355 | 89 | 2026-06-29 → 2026-11-03 |
| TATASTEEL.NS | 494 | 444 | 355 | 89 | 2026-06-29 → 2026-11-03 |

The feature date is the session whose close is known. The target date is the
next trading session. Each report stores both, plus the actual next open used by
the backtester.

## 3. Fold construction

For each symbol:

1. Build the causal features and next-day target.
2. Reserve the most recent 20% as the final holdout.
3. Split the remaining development rows into chronological expanding folds.
4. For each fold, train on a prefix and validate on the next block.
5. Check that every training target date is strictly earlier than the first
   validation target date.
6. Refit fresh models (including a fresh SVR scaler) on each fold.
7. Pool the validation predictions across folds for the development metrics.

The final holdout is evaluated only after selection is recorded. All candidates
are refit on development data that precedes the holdout.

## 4. Metrics

Percentages are reported as percentages (for example, `12.5` means `12.5%`), not
as fractions.

### 4.1 Price and error metrics

| Metric | Definition | Interpretation |
|--------|------------|----------------|
| MAE | mean of `|actual − predicted|` | Average absolute price error in currency units |
| MSE | mean of `(actual − predicted)²` | Squared error, same units squared |
| RMSE | `sqrt(MSE)` | Average error with larger errors penalized; primary selection metric |
| R² | `1 − SS_res / SS_tot` | Share of variance explained; can be negative; not used for selection |
| sMAPE | mean of `2|actual − predicted| / (|actual| + |predicted|) × 100` | Scale-aware percentage error; handles zero actual values |
| MAPE | mean of `|actual − predicted| / |actual| × 100` | Supplementary; rows with zero actual are excluded |
| NMAE | `MAE / mean(|current price|) × 100` | Error relative to the price level, comparable across stocks |
| NRMSE | `RMSE / mean(|current price|) × 100` | RMSE relative to the price level |
| MASE vs random walk | `MAE / mean(|actual − current|)` | `< 1` means lower error than a random-walk forecast |

`current` is the feature-day close. For return forecasts, the caller passes
zeros as the current value so the return itself is the movement.

### 4.2 Directional metrics

Let `actual_movement = actual − current` and
`predicted_movement = predicted − current`.

- **Signal**: a prediction with non-zero predicted movement.
- **Abstention**: a prediction with exactly zero predicted movement.
- **Directional signal sample**: a row where the prediction signaled and the
  actual price also moved.
- **Directional accuracy**: correct directional signals / directional signal
  samples × 100. It is `null` when there are no directional signal samples.
- **Signal coverage**: signaled rows / eligible rows × 100.
- **Coverage of moving days**: signaled-and-moved rows / moved rows × 100.
- **Abstention rate**: abstaining rows / eligible rows × 100.

The naive-persistence baseline predicts the current close, so its predicted
movement is zero. It therefore has:

```text
directional_accuracy = null
signal_coverage = 0
abstention_rate = 100
```

It is **not** assigned a directional accuracy of zero. A baseline that abstains
does not create a misleading directional win or loss for a candidate.

### 4.3 Return metrics

For return targets, the service reports:

- `return_mae` and `return_rmse` on the native return scale;
- `relative_return_mae` and `relative_return_rmse`, dividing by the mean absolute
  actual return;
- reconstructed-price MAE/RMSE and the same normalized and directional metrics
  used for absolute prices.

The zero-return baseline is identical across families in price space: it
reconstructs the current close.

## 5. Selection protocol

1. Compute pooled development walk-forward metrics for:
   - the five ML models;
   - the equal-weight ensemble;
   - the naive-persistence baseline.
2. Rank all candidates by RMSE, then MAE, then directional accuracy.
3. Select from the **deployable set** (five ML models + ensemble). The baseline
   is excluded from deployable selection but remains in the comparison.
4. Record the selection and rankings in the report.
5. Refit the candidates on development data before the holdout.
6. Evaluate the locked holdout once.
7. Report the selected model's holdout metrics, the best holdout model, and the
   baseline comparison separately.

The holdout is never used to change the selected model.

## 6. Actual Phase 2 results

The development-selected model was `linear_regression` for all six symbols. The
naive-persistence baseline had lower RMSE than the selected model and the
equal-weight ensemble on every holdout.

| Symbol | Selected dev RMSE | Baseline dev RMSE | Selected holdout RMSE | Baseline holdout RMSE | Ensemble holdout RMSE | Selected holdout direction | Ensemble holdout direction |
|--------|-------------------|-------------------|-----------------------|-----------------------|-----------------------|----------------------------|----------------------------|
| COALINDIA.NS | 7.1656 | **6.4567** | 5.2904 | **5.1340** | 9.8415 | 47.13% | 48.28% |
| HINDALCO.NS | 18.9366 | **18.3421** | 16.0471 | **14.9091** | 19.2646 | 53.93% | 50.56% |
| HINDZINC.NS | 17.2757 | **15.2537** | 11.2199 | **11.0827** | 11.7107 | 50.56% | 53.93% |
| JINDALSTEL.NS | 23.1711 | **21.1350** | 17.9109 | **17.3097** | 19.3793 | 51.69% | 53.93% |
| JSWSTEEL.NS | 19.8433 | **18.8561** | 20.0331 | **19.9396** | 26.7991 | 52.81% | 51.69% |
| TATASTEEL.NS | 3.5638 | **3.3607** | 2.6784 | **2.5096** | 4.4366 | 43.82% | 41.57% |

The ensemble beat the persistence baseline on RMSE in neither development nor
holdout for any symbol. Directional accuracy was close to a coin flip and varied
by symbol; the baseline abstained and therefore has no directional score.

### 6.1 Holdout normalized errors

| Symbol | Selected NRMSE | Baseline NRMSE | Selected MASE vs random walk |
|--------|----------------|----------------|------------------------------|
| COALINDIA.NS | 1.3159% | 1.2770% | 1.0615 |
| HINDALCO.NS | 1.6549% | 1.5376% | 1.1022 |
| HINDZINC.NS | 2.0168% | 1.9922% | 1.0143 |
| JINDALSTEL.NS | 1.6463% | 1.5911% | 1.0190 |
| JSWSTEEL.NS | 1.5883% | 1.5809% | 1.0126 |
| TATASTEEL.NS | 1.4603% | 1.3682% | 1.1234 |

MASE values above 1.0 indicate that the selected models had higher absolute
error than a random-walk forecast on these holdouts.

## 7. Actual Phase 2.1 results

The return-target experiment compared absolute-price, simple-return, and
log-return formulations on identical folds and holdout boundaries.

For **every symbol and every family**, the best reconstructed-price model was
`zero_return_persistence`. For every symbol, the best family by
reconstructed-price RMSE and by return RMSE was `absolute_price`.

| Symbol | Zero-return price RMSE (all families) | Return RMSE | Return MAE |
|--------|----------------------------------------|-------------|------------|
| COALINDIA.NS | **5.1348** | 0.012884 | 0.008942 |
| HINDALCO.NS | **14.9097** | 0.015250 | 0.012149 |
| HINDZINC.NS | **11.0819** | 0.019581 | 0.015546 |
| JINDALSTEL.NS | **17.3198** | 0.015925 | 0.013042 |
| JSWSTEEL.NS | **19.9402** | 0.016003 | 0.011843 |
| TATASTEEL.NS | **2.5095** | 0.013895 | 0.010577 |

The zero-return baseline's directional metrics remain `null` accuracy, 0%
coverage, and 100% abstention. The return experiment did not produce evidence
that a return-target formulation beats the zero-return benchmark on this data.

## 8. Interpretation

- The current ML models did not beat a naive random-walk/persistence forecast on
  the six holdouts. This is the central empirical result and is reported without
  adjustment.
- Directional accuracy near 50% is consistent with weak directional skill on
  this sample; it is not evidence of an exploitable edge.
- The equal-weight ensemble was not better than its components in these
  holdouts; on several symbols it was materially worse.
- The return-target experiment did not rescue the price forecasts.
- The holdout is one historical path of 89 sessions per symbol. These results are
  not statistically strong enough to support live trading, and they should not
  be presented as profitable.

## 9. Reproducibility and limitations

- Each report stores a SHA-256 fingerprint of the cleaned OHLCV data, the
  configuration, fold metadata, and the report schema version.
- Live `yfinance` history can change; a rerun may use revised data.
- The evaluation uses a single fixed holdout and five requested folds; no
  repeated nested cross-validation is performed.
- Model selection is limited to the five predefined models and a fixed ensemble.
- No statistical significance test or multiple-comparison correction is applied
  to the symbol-level results.
- Metrics are computed on the available finite rows; missing or non-finite values
  are excluded by the metric functions.
- A backtest on the same forecasts is a separate simulation and inherits these
  limitations. See [BACKTESTING_METHODOLOGY.md](BACKTESTING_METHODOLOGY.md).
