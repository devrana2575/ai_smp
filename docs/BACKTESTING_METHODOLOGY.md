# Backtesting Methodology

This document describes the Phase 3 research backtester, its execution model,
cost assumptions, strategy definitions, risk metrics, and the actual simulated
results in this repository. The backtester is a research tool, not a live
trading system and not evidence of future profitability.

## 1. Purpose and scope

The backtester answers a narrow question: if a walk-forward forecast had been
traded mechanically on this historical path, with simplified costs and next-open
execution, what would the equity curve and trade statistics look like?

It deliberately does **not** model:

- market impact, queue position, or partial fills;
- intraday prices, gaps, or limit-order behavior;
- borrow costs, short selling, leverage, margin calls, or taxes;
- corporate actions beyond the adjusted OHLCV returned by `yfinance`;
- liquidity constraints or position-size limits relative to volume;
- survivorship bias in the selected symbol universe.

## 2. Inputs

The backtest consumes the Phase 2 walk-forward report for a symbol. It uses the
pooled out-of-sample rows:

- development validation predictions across the expanding folds;
- the locked final-holdout predictions.

Each row contains:

| Field | Meaning |
|-------|---------|
| `signal_date` | Feature-day session whose close is known |
| `target_date` | Next trading session |
| `current_close` | Close on the signal date |
| `next_open` | Open on the target date; execution price |
| `next_close` | Close on the target date; mark-to-market price |
| `predicted_close` | Model or ensemble forecast for the target close |
| `model_name` | Forecast source |

The live reports contain 266 pooled out-of-sample rows per symbol, covering
first signal dates in early October 2025 and last execution dates on
2026-11-04 (JINDALSTEL starts 2025-10-03 because its history differs by one
session). The rows combine the walk-forward development validation period and
the final holdout; they are not a second holdout or a fresh sample.

## 3. Execution model

1. A signal is formed after the **signal-day close**.
2. The order is executed at the **next session's open**.
3. The position is marked to market at the **next session's close**.
4. Slippage is applied to the execution price:
   - buy: `open × (1 + slippage_bps / 10,000)`;
   - sell: `open × (1 − slippage_bps / 10,000)`.
5. A proportional commission is charged on the traded notional:
   `notional × transaction_cost_bps / 10,000`.
6. Long-only; one position at a time; no pyramiding.
7. Position size is bounded by `max_capital_allocation` of available cash
   (default 100%). The engine solves for share count including commission so
   cash cannot go negative.
8. At the end of the path, an open position is liquidated at the final close
   solely for consistent trade accounting. The liquidation cost is included and
   flagged as `forced_liquidation`. This is not a live-trading assumption.

The next-open rule prevents the simulation from trading on the same close used
to construct the signal.

## 4. Default configuration

| Parameter | Default |
|-----------|---------|
| Starting capital | 100,000 |
| Transaction cost | 5 bps per side |
| Slippage | 5 bps per side |
| Max capital allocation | 1.0 (100%) |
| Buy threshold | +0.5% predicted return |
| Sell threshold | −0.5% predicted return |
| Risk-free rate | 0.0 |
| Trading days per year | 252 |
| Final liquidation | Enabled |
| Signal source | Development-selected model |

The defaults are configurable through `BacktestRequest` and the
`BACKTEST_*` environment variables. The backtest report records the exact
configuration used.

## 5. Strategies

| Strategy | Rule | Interpretation |
|----------|------|----------------|
| `buy_and_hold` | Enter at the first execution open and hold until final liquidation | Market exposure benchmark |
| `cash` | Never enter | Zero-return benchmark |
| `persistence` | The naive forecast is the current close; predicted movement is zero, so the strategy abstains and holds cash | No-trade benchmark |
| `model_directional` | Long when `predicted_close > current_close`; exit when the prediction is not above the current close | Uses the sign of the forecast |
| `threshold` | Enter when predicted return > `buy_threshold`; while long, stay until predicted return < `sell_threshold` | Reduces low-conviction turnover |

`cash` and `persistence` are expected to return exactly 0% before costs because
they never trade. They are included to make the opportunity cost of trading
explicit.

## 6. Metrics

### 6.1 Equity metrics

Let `E_t` be the equity at the end of period `t`, `E_0` the starting capital, and
`r_t = E_t / E_{t-1} − 1` the period return.

| Metric | Definition |
|--------|------------|
| Final equity | Last equity-curve value |
| Total return | `E_T / E_0 − 1` |
| Annualized return | `(E_T / E_0)^(252 / n) − 1` when `n > 0` and total return > −100% |
| Annualized volatility | Sample standard deviation of `r_t` × `sqrt(252)` |
| Sharpe ratio | Mean excess period return / period volatility × `sqrt(252)` |
| Sortino ratio | Mean excess period return / downside deviation × `sqrt(252)` |
| Max drawdown | Minimum of `E_t / running_peak − 1` |
| Calmar ratio | Annualized return / absolute max drawdown |
| Best/worst period | Maximum/minimum daily return |

Annualized return is a compound growth rate. Sharpe and Sortino use the
arithmetic mean of period returns, so they can disagree in sign with the
compounded return on volatile paths. That is a property of the definitions, not
a hidden adjustment.

### 6.2 Trade metrics

Only closed trades enter win rate, profit factor, and average-trade statistics.
Open trades are marked to market in the equity curve but are not counted as
wins. If there are no losing trades, profit factor is reported as `null` rather
than infinity or a fabricated number.

| Metric | Definition |
|--------|------------|
| Closed trades | Trades with an exit |
| Win rate | Winning closed trades / closed trades |
| Gross profit / loss | Sum of positive / negative net P&L |
| Profit factor | Gross profit / absolute gross loss, or `null` if undefined |
| Average trade return | Mean net P&L / entry notional across closed trades |
| Average holding days | Mean `exit_index − entry_index` |
| Transaction costs | Sum of entry and exit commissions (slippage is embedded in execution prices) |

P&L is net of commission. Slippage is already reflected in the entry/exit
prices, so it is not double-counted in the `transaction_costs` field.

### 6.3 Monthly returns and equity curve

The report includes a daily equity curve with cash, shares, position value,
equity, close, drawdown, and long/flat state. Monthly returns are calendar-month
changes in equity. Equity-curve CSV files contain the full daily path.

## 7. Actual simulated results

The table below is the actual output of
`backtesting_reports/backtest_summary.csv` for the live reports. It is a
historical simulation with the default costs, not a forecast of future returns.

| Symbol | Strategy | Total return | Annualized return | Annualized vol | Sharpe | Max drawdown | Closed trades | Win rate | Transaction costs |
|--------|----------|--------------|-------------------|----------------|--------|--------------|---------------|----------|-------------------|
| COALINDIA.NS | buy_and_hold | 13.94% | 13.16% | 23.63% | 0.64 | −17.12% | 1 | 100.00% | 106.97 |
| COALINDIA.NS | model_directional | 3.95% | 3.74% | 18.48% | 0.29 | −15.37% | 27 | 51.85% | 2,841.73 |
| COALINDIA.NS | threshold | −2.21% | −2.09% | 18.78% | −0.02 | −16.62% | 10 | 50.00% | 1,053.34 |
| HINDALCO.NS | buy_and_hold | 18.23% | 17.19% | 28.66% | 0.70 | −23.95% | 1 | 100.00% | 109.12 |
| HINDALCO.NS | model_directional | 0.67% | 0.64% | 25.84% | 0.15 | −25.33% | 29 | 55.17% | 3,030.56 |
| HINDALCO.NS | threshold | 9.43% | 8.91% | 24.25% | 0.47 | −19.35% | 4 | 50.00% | 450.76 |
| HINDZINC.NS | buy_and_hold | 7.81% | 7.38% | 38.02% | 0.38 | −32.94% | 1 | 100.00% | 103.90 |
| HINDZINC.NS | model_directional | −31.97% | −30.58% | 25.03% | −1.33 | −40.69% | 25 | 36.00% | 1,988.94 |
| HINDZINC.NS | threshold | −20.89% | −19.91% | 18.12% | −1.13 | −23.72% | 3 | 0.00% | 260.16 |
| JINDALSTEL.NS | buy_and_hold | 3.78% | 3.58% | 28.21% | 0.27 | −21.49% | 1 | 100.00% | 101.89 |
| JINDALSTEL.NS | model_directional | −1.10% | −1.05% | 23.16% | 0.07 | −15.55% | 25 | 56.00% | 2,573.01 |
| JINDALSTEL.NS | threshold | 5.19% | 4.91% | 24.32% | 0.32 | −20.98% | 8 | 62.50% | 825.52 |
| JSWSTEEL.NS | buy_and_hold | 14.64% | 13.82% | 25.41% | 0.64 | −13.35% | 1 | 100.00% | 107.33 |
| JSWSTEEL.NS | model_directional | 2.05% | 1.94% | 20.51% | 0.20 | −13.11% | 34 | 44.12% | 3,406.96 |
| JSWSTEEL.NS | threshold | 17.17% | 16.19% | 20.67% | 0.83 | −12.90% | 5 | 80.00% | 524.93 |
| TATASTEEL.NS | buy_and_hold | 5.19% | 4.91% | 26.20% | 0.31 | −22.64% | 1 | 100.00% | 102.60 |
| TATASTEEL.NS | model_directional | −5.29% | −5.02% | 19.19% | −0.17 | −17.57% | 28 | 60.71% | 2,904.49 |
| TATASTEEL.NS | threshold | −7.84% | −7.44% | 19.16% | −0.31 | −15.88% | 6 | 33.33% | 584.38 |

`cash` and `persistence` returned 0.00% for every symbol, with no trades and no
costs. They are omitted from the table for brevity.

### 7.1 Highest-return strategy by symbol

| Symbol | Highest simulated return |
|--------|--------------------------|
| COALINDIA.NS | buy_and_hold (13.94%) |
| HINDALCO.NS | buy_and_hold (18.23%) |
| HINDZINC.NS | buy_and_hold (7.81%) |
| JINDALSTEL.NS | threshold (5.19%) |
| JSWSTEEL.NS | threshold (17.17%) |
| TATASTEEL.NS | buy_and_hold (5.19%) |

### 7.2 What the results show

- Buy-and-hold was the highest-return strategy on four of six symbols.
- The model-directional strategy lost money on HINDZINC, JINDALSTEL, and
  TATASTEEL; it was profitable on COALINDIA, HINDALCO, and JSWSTEEL but below
  buy-and-hold on all three.
- The threshold strategy beat buy-and-hold on JINDALSTEL and JSWSTEEL, but lost
  money on COALINDIA, HINDZINC, and TATASTEEL.
- The persistence and cash benchmarks returned zero. This is expected: the
  persistence forecast predicts no movement and therefore does not trade.
- Transaction costs are material for the high-turnover model-directional
  strategy (roughly 1,989–3,407 currency units over the path), while buy-and-hold
  pays only entry and final-liquidation costs.
- A strategy winning on one path does not establish skill. The sample is short,
  single-path, and sensitive to the evaluation window.

## 8. Report artifacts

For each symbol, `save_report()` writes:

- `{SYMBOL}_backtest.json` — configuration, data fingerprint, all strategy
  results, trade lists, equity curves, monthly returns, comparisons, sensitivity
  scenarios, assumptions, reproducibility metadata, warnings, and limitations;
- `{SYMBOL}_equity_curve.csv` — daily equity path for every strategy;
- `{SYMBOL}_trades.csv` — closed-trade records;
- `{SYMBOL}_strategy_comparison.csv` — one row per strategy.

A combined `backtest_summary.csv` is written at the report root. The CLI runner
is `scripts/run_backtesting.py`.

## 9. Cost, slippage, and threshold sensitivity

The backtest report includes a `sensitivity` block with three analyses. All
scenarios reuse the same chronological prediction rows and the same next-open
execution rule; only the stated assumption changes.

1. **Cost/slippage grid.** Default cost scenarios are `0, 5, 10, 25, 50` bps and
   default slippage scenarios are `0, 5, 10, 25` bps. The default analysis is the
   20-point cross-product. Each scenario reports total return, annualized
   return, Sharpe, maximum drawdown, final equity, closed trades, and total
   transaction costs for the model-directional, threshold, and buy-and-hold
   strategies.
2. **Threshold sensitivity.** Default buy/sell threshold pairs are `(0, 0)`,
   `(0.005, -0.005)`, `(0.01, -0.01)`, and `(0.02, -0.02)`. Each row reports the
   same strategy metrics for the threshold strategy.
3. **Configurability.** API callers may supply up to 20 values per list. Lists
   and threshold pairs are validated before the job starts. `run_sensitivity:
   false` records that the analysis was skipped.

A large grid increases multiple-comparison risk. The best-looking scenario is
descriptive and should not be presented as a forecast or as evidence of
guaranteed profitability. See [API_DOCUMENTATION.md](API_DOCUMENTATION.md) for
the request fields.

## 10. Reproducibility

The report records the walk-forward source report ID and SHA-256 hash, the exact
backtest configuration, the sensitivity configuration, the model name, the
evaluation configuration, feature schema, random seed, dataset period,
data fingerprint, data source, synthetic-data flag, and generation time.

Signal and execution dates are validated: every execution date must be strictly
after its signal date. Rerunning on revised `yfinance` history will change the
result; the fingerprint makes that visible. Reports derived from the synthetic
test fixture are labelled `synthetic_test_data` and are not market evidence.

## 11. Limitations and responsible use

- One historical path cannot distinguish skill from luck.
- The backtest trades the same walk-forward predictions used for evaluation;
  this is an in-sample reuse of out-of-sample predictions, not a new holdout.
- Simplified fills and proportional costs ignore market impact and liquidity.
- The forced final liquidation is an accounting convention, not a trading rule.
- The strategy set is small and was chosen for interpretability, not optimized
  on the holdout.
- Cost/slippage and threshold scenarios multiply the number of comparisons; the
  best scenario is especially prone to selection bias.
- No result here is a recommendation to buy, sell, or hold any security.
