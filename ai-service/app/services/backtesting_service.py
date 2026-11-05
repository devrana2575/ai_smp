"""Chronological backtesting for research forecasts.

The backtester consumes out-of-sample walk-forward predictions from the Phase 2
evaluation report. A signal is formed from the feature-day close and executed
at the next session's open, so the simulation never trades on the same close it
used to forecast. Transaction costs and slippage are charged on both sides.

This is a research simulation, not a live trading system. It does not model
market impact, liquidity, borrow, taxes, corporate actions, or intraday fills.
"""

from __future__ import annotations

import csv
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from app.config import settings
from app.services.data_service import validate_symbol
from app.services.risk_metrics_service import (
    calculate_equity_metrics,
    calculate_trade_metrics,
    compare_strategies,
    drawdown_series,
    monthly_returns,
)
from app.services.walk_forward_evaluation import (
    _json_safe,
    walk_forward_evaluation_service,
)


STRATEGY_BUY_HOLD = "buy_and_hold"
STRATEGY_CASH = "cash"
STRATEGY_PERSISTENCE = "persistence"
STRATEGY_MODEL = "model_directional"
STRATEGY_THRESHOLD = "threshold"
STRATEGY_NAMES: Tuple[str, ...] = (
    STRATEGY_BUY_HOLD,
    STRATEGY_CASH,
    STRATEGY_PERSISTENCE,
    STRATEGY_MODEL,
    STRATEGY_THRESHOLD,
)
STRATEGY_LABELS = {
    STRATEGY_BUY_HOLD: "Buy and Hold",
    STRATEGY_CASH: "Cash (No Position)",
    STRATEGY_PERSISTENCE: "Persistence Signal (zero expected return)",
    STRATEGY_MODEL: "Model Directional (selected forecast)",
    STRATEGY_THRESHOLD: "Threshold Return Strategy",
}
STRATEGY_DESCRIPTIONS = {
    STRATEGY_BUY_HOLD: (
        "Buy at the first evaluation session's open and hold until the final "
        "close; forced liquidation at the final close for trade accounting."
    ),
    STRATEGY_CASH: "Hold cash for the entire evaluation period.",
    STRATEGY_PERSISTENCE: (
        "Use the persistence forecast (next close equals current close) as the "
        "signal. Because the forecast is exactly zero movement, it abstains "
        "and remains in cash rather than receiving an artificial directional "
        "trade."
    ),
    STRATEGY_MODEL: (
        "Go long at the next open when the selected model forecasts a higher "
        "next close than the current close; exit to cash when it forecasts a "
        "lower or unchanged close."
    ),
    STRATEGY_THRESHOLD: (
        "Go long when the model's predicted return exceeds the buy threshold; "
        "exit when it falls below the sell threshold; otherwise retain the "
        "current position. Long-only, one position at a time."
    ),
}


@dataclass(frozen=True)
class BacktestConfig:
    starting_capital: float = settings.BACKTEST_STARTING_CAPITAL
    transaction_cost_bps: float = settings.BACKTEST_TRANSACTION_COST_BPS
    slippage_bps: float = settings.BACKTEST_SLIPPAGE_BPS
    max_capital_allocation: float = (
        settings.BACKTEST_MAX_CAPITAL_ALLOCATION
    )
    buy_threshold: float = settings.BACKTEST_BUY_THRESHOLD
    sell_threshold: float = settings.BACKTEST_SELL_THRESHOLD
    risk_free_rate: float = settings.RISK_FREE_RATE
    periods_per_year: int = settings.TRADING_DAYS_PER_YEAR
    model_name: Optional[str] = None
    signal_source: str = "selected"
    liquidate_at_end: bool = True

    def validate(self) -> None:
        if self.starting_capital <= 0:
            raise ValueError("starting_capital must be positive")
        if self.transaction_cost_bps < 0:
            raise ValueError("transaction_cost_bps cannot be negative")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps cannot be negative")
        if not 0 < self.max_capital_allocation <= 1:
            raise ValueError("max_capital_allocation must be in (0, 1]")
        if self.buy_threshold < self.sell_threshold:
            raise ValueError("buy_threshold must be >= sell_threshold")
        if self.periods_per_year <= 0:
            raise ValueError("periods_per_year must be positive")
        if self.signal_source not in {"selected", "ensemble"}:
            raise ValueError("signal_source must be 'selected' or 'ensemble'")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "starting_capital": self.starting_capital,
            "transaction_cost_bps": self.transaction_cost_bps,
            "slippage_bps": self.slippage_bps,
            "max_capital_allocation": self.max_capital_allocation,
            "buy_threshold": self.buy_threshold,
            "sell_threshold": self.sell_threshold,
            "risk_free_rate": self.risk_free_rate,
            "periods_per_year": self.periods_per_year,
            "model_name": self.model_name,
            "signal_source": self.signal_source,
            "liquidate_at_end": self.liquidate_at_end,
        }

    @classmethod
    def from_settings(cls) -> "BacktestConfig":
        return cls()


class BacktestingService:
    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        evaluation_service: Any = None,
        report_dir: Optional[str] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.config = config or BacktestConfig()
        self.evaluation_service = (
            evaluation_service or walk_forward_evaluation_service
        )
        self.report_dir = report_dir or settings.BACKTEST_REPORT_DIR
        self.now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
        )

    # ------------------------------------------------------------------
    # Signal-row extraction
    # ------------------------------------------------------------------
    def _resolve_model(self, report: Mapping[str, Any], config: BacktestConfig) -> str:
        if config.model_name:
            return config.model_name
        if config.signal_source == "ensemble":
            return "ensemble_equal_weight"
        selected = (
            report.get("best_performing_model", {}).get("selected_model")
        )
        if selected:
            return str(selected)
        return "ensemble_equal_weight"

    def extract_rows(
        self,
        report: Mapping[str, Any],
        model_name: str,
    ) -> List[Dict[str, Any]]:
        sections: List[Mapping[str, Any]] = [
            fold["validation"]
            for fold in report.get("development_validation", {}).get(
                "folds", []
            )
            if fold.get("status") == "ok"
        ]
        holdout = report.get("final_holdout", {}).get("validation")
        if holdout:
            sections.append(holdout)

        rows: List[Dict[str, Any]] = []
        for validation in sections:
            predictions = validation.get("predictions", {})
            if model_name not in predictions:
                continue
            dates = validation.get("dates", [])
            target_dates = validation.get("target_dates", [])
            current = validation.get("current_close", [])
            next_open = validation.get("actual_next_open", [])
            next_close = validation.get("actual_next_close", [])
            predicted = predictions.get(model_name, [])
            if not (
                len(dates)
                == len(target_dates)
                == len(current)
                == len(next_open)
                == len(next_close)
                == len(predicted)
            ):
                raise ValueError(
                    "Validation arrays have inconsistent lengths for "
                    f"{model_name}"
                )
            for index in range(len(dates)):
                values = {
                    "signal_date": str(dates[index]),
                    "target_date": str(target_dates[index]),
                    "current_close": float(current[index]),
                    "next_open": float(next_open[index]),
                    "next_close": float(next_close[index]),
                    "predicted_close": float(predicted[index]),
                    "model_name": model_name,
                }
                for key, value in values.items():
                    if key.endswith("_close") or key == "next_open":
                        if not math.isfinite(value) or value <= 0:
                            raise ValueError(
                                f"Non-positive or non-finite {key} for "
                                f"{values['target_date']}"
                            )
                if not math.isfinite(values["predicted_close"]):
                    raise ValueError("Predicted close is not finite")
                rows.append(values)

        if not rows:
            raise ValueError(
                "No out-of-sample prediction rows were available for "
                f"model {model_name}"
            )

        rows.sort(key=lambda row: (row["target_date"], row["signal_date"]))
        target_dates = [row["target_date"] for row in rows]
        if len(set(target_dates)) != len(target_dates):
            raise ValueError("Backtest target dates contain duplicates")
        return rows

    # ------------------------------------------------------------------
    # Simulation
    # ------------------------------------------------------------------
    def _wants_long(
        self,
        strategy: str,
        row: Mapping[str, Any],
        currently_long: bool,
        config: BacktestConfig,
    ) -> bool:
        if strategy == STRATEGY_BUY_HOLD:
            return True
        if strategy == STRATEGY_CASH:
            return False
        if strategy == STRATEGY_PERSISTENCE:
            # Persistence predicts exactly the current close. It abstains.
            return False
        if strategy == STRATEGY_MODEL:
            return float(row["predicted_close"]) > float(
                row["current_close"]
            )
        if strategy == STRATEGY_THRESHOLD:
            predicted_return = (
                float(row["predicted_close"]) / float(row["current_close"])
                - 1.0
            )
            if currently_long:
                return predicted_return >= config.sell_threshold
            return predicted_return > config.buy_threshold
        raise ValueError(f"Unknown strategy: {strategy}")

    def simulate_strategy(
        self,
        rows: Sequence[Mapping[str, Any]],
        strategy: str,
        config: Optional[BacktestConfig] = None,
    ) -> Dict[str, Any]:
        active = config or self.config
        active.validate()
        if strategy not in STRATEGY_NAMES:
            raise ValueError(f"Unknown strategy: {strategy}")
        if not rows:
            raise ValueError("Backtest requires at least one row")

        cash = float(active.starting_capital)
        shares = 0.0
        entry: Optional[Dict[str, Any]] = None
        trades: List[Dict[str, Any]] = []
        equity_curve: List[Dict[str, Any]] = []
        cost_rate = active.transaction_cost_bps / 10_000.0
        slippage_rate = active.slippage_bps / 10_000.0

        for index, row in enumerate(rows):
            currently_long = shares > 1e-12
            wants_long = self._wants_long(
                strategy, row, currently_long, active
            )
            open_price = float(row["next_open"])
            close_price = float(row["next_close"])

            if wants_long and not currently_long:
                effective_price = open_price * (1.0 + slippage_rate)
                budget = cash * active.max_capital_allocation
                if budget > 0 and effective_price > 0:
                    max_shares = budget / (
                        effective_price * (1.0 + cost_rate)
                    )
                    commission = max_shares * effective_price * cost_rate
                    total = max_shares * effective_price + commission
                    if total > cash:
                        max_shares *= cash / total
                        commission = (
                            max_shares * effective_price * cost_rate
                        )
                        total = max_shares * effective_price + commission
                    if max_shares > 0 and total <= cash + 1e-9:
                        shares = max_shares
                        cash -= total
                        entry = {
                            "entry_signal_date": row["signal_date"],
                            "entry_date": row["target_date"],
                            "entry_index": index,
                            "entry_price": effective_price,
                            "shares": shares,
                            "entry_notional": shares * effective_price,
                            "entry_cost": commission,
                            "model_name": row.get("model_name"),
                        }

            elif not wants_long and currently_long:
                effective_price = open_price * (1.0 - slippage_rate)
                proceeds = shares * effective_price
                commission = proceeds * cost_rate
                net_proceeds = proceeds - commission
                cash += net_proceeds
                if entry is not None:
                    total_cost = entry["entry_cost"] + commission
                    net_pnl = net_proceeds - (
                        entry["entry_notional"] + entry["entry_cost"]
                    )
                    trades.append(
                        {
                            **entry,
                            "exit_date": row["target_date"],
                            "exit_index": index,
                            "exit_price": effective_price,
                            "exit_notional": proceeds,
                            "exit_cost": commission,
                            "total_costs": total_cost,
                            "net_pnl": net_pnl,
                            "net_return_pct": (
                                net_pnl
                                / (
                                    entry["entry_notional"]
                                    + entry["entry_cost"]
                                )
                                * 100.0
                                if entry["entry_notional"]
                                else None
                            ),
                            "holding_days": index - entry["entry_index"],
                            "status": "closed",
                            "forced_liquidation": False,
                        }
                    )
                shares = 0.0
                entry = None

            position_value = shares * close_price
            equity = cash + position_value
            equity_curve.append(
                {
                    "date": row["target_date"],
                    "signal_date": row["signal_date"],
                    "cash": cash,
                    "position_shares": shares,
                    "position_value": position_value,
                    "equity": equity,
                    "close": close_price,
                    "predicted_close": row.get("predicted_close"),
                    "currently_long": shares > 1e-12,
                }
            )

        # Force liquidation at the final close solely for consistent trade
        # accounting. This is disclosed in the report and is not a live trading
        # assumption.
        if active.liquidate_at_end and shares > 1e-12 and equity_curve:
            final_close = float(rows[-1]["next_close"])
            effective_price = final_close * (1.0 - slippage_rate)
            proceeds = shares * effective_price
            commission = proceeds * cost_rate
            net_proceeds = proceeds - commission
            cash += net_proceeds
            if entry is not None:
                total_cost = entry["entry_cost"] + commission
                net_pnl = net_proceeds - (
                    entry["entry_notional"] + entry["entry_cost"]
                )
                trades.append(
                    {
                        **entry,
                        "exit_date": rows[-1]["target_date"],
                        "exit_index": len(rows) - 1,
                        "exit_price": effective_price,
                        "exit_notional": proceeds,
                        "exit_cost": commission,
                        "total_costs": total_cost,
                        "net_pnl": net_pnl,
                        "net_return_pct": (
                            net_pnl
                            / (entry["entry_notional"] + entry["entry_cost"])
                            * 100.0
                            if entry["entry_notional"]
                            else None
                        ),
                        "holding_days": len(rows) - 1 - entry["entry_index"],
                        "status": "closed",
                        "forced_liquidation": True,
                    }
                )
            shares = 0.0
            entry = None
            equity_curve[-1].update(
                {
                    "cash": cash,
                    "position_shares": 0.0,
                    "position_value": 0.0,
                    "equity": cash,
                    "forced_liquidation": True,
                }
            )

        drawdowns = drawdown_series(equity_curve)
        for point, drawdown in zip(equity_curve, drawdowns):
            point.update(
                {
                    "peak_equity": drawdown["peak_equity"],
                    "drawdown": drawdown["drawdown"],
                    "drawdown_pct": drawdown["drawdown_pct"],
                }
            )

        equity_metrics = calculate_equity_metrics(
            equity_curve,
            active.starting_capital,
            risk_free_rate=active.risk_free_rate,
            periods_per_year=active.periods_per_year,
        )
        trade_metrics = calculate_trade_metrics(trades)
        monthly = monthly_returns(equity_curve)
        warnings: List[str] = []
        if strategy == STRATEGY_PERSISTENCE:
            warnings.append(
                "The persistence forecast predicts zero movement and therefore "
                "abstains from trading; this strategy holds cash by design."
            )
        if not trades:
            warnings.append("No trades were generated by this strategy.")
        if any(trade.get("forced_liquidation") for trade in trades):
            warnings.append(
                "The final open position was liquidated at the final close for "
                "trade accounting; the liquidation cost is included."
            )

        return {
            "strategy": strategy,
            "label": STRATEGY_LABELS[strategy],
            "description": STRATEGY_DESCRIPTIONS[strategy],
            "status": "ok",
            "equity_curve": equity_curve,
            "trades": trades,
            "equity_metrics": equity_metrics,
            "trade_metrics": trade_metrics,
            "monthly_returns": monthly,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Full symbol run
    # ------------------------------------------------------------------
    def run_symbol(
        self,
        symbol: str,
        config: Optional[BacktestConfig] = None,
        evaluation_report: Optional[Mapping[str, Any]] = None,
        write_report: bool = True,
        output_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        active = config or self.config
        active.validate()
        normalized = validate_symbol(symbol)
        report = evaluation_report
        if report is None:
            report = self.evaluation_service.evaluate_symbol(
                normalized, write_report=False
            )
        model_name = self._resolve_model(report, active)
        rows = self.extract_rows(report, model_name)
        results = {
            strategy: self.simulate_strategy(rows, strategy, active)
            for strategy in STRATEGY_NAMES
        }
        comparison = compare_strategies(results)
        best_return_strategy = None
        candidates = [
            row
            for row in comparison
            if row["total_return_pct"] is not None
        ]
        if candidates:
            best_return_strategy = max(
                candidates, key=lambda row: row["total_return_pct"]
            )["strategy"]

        warnings = [
            "This is a historical simulation using out-of-sample walk-forward "
            "predictions, not a live trading record.",
            "Transaction costs and slippage are simplified proportional "
            "charges; market impact, liquidity, taxes, and borrow costs are "
            "not modeled.",
            "Signals are formed at the feature-day close and executed at the "
            "next session's open. The simulation cannot guarantee that a fill "
            "would have been available at that price.",
            "Buy-and-hold, cash, persistence, model, and threshold strategies "
            "are benchmarks; no strategy is endorsed as profitable.",
        ]
        if best_return_strategy:
            warnings.append(
                f"The highest simulated total return in this single period was "
                f"{best_return_strategy}; this is descriptive and is not a "
                "claim of future performance."
            )

        output: Dict[str, Any] = {
            "schema_version": "1.0",
            "experiment": "walk_forward_backtesting",
            "symbol": normalized,
            "generated_at": self.now_provider()
            .astimezone(timezone.utc)
            .isoformat(),
            "status": "completed",
            "production_inference_changed": False,
            "config": active.to_dict(),
            "model": {
                "name": model_name,
                "source": (
                    "configured"
                    if active.model_name
                    else (
                        "ensemble"
                        if active.signal_source == "ensemble"
                        else "development selected model"
                    )
                ),
                "selected_model_in_report": report.get(
                    "best_performing_model", {}
                ).get("selected_model"),
                "selection_uses_holdout": False,
            },
            "data": {
                "source": "yfinance",
                "evaluation_period": report.get("data", {}).get("period"),
                "data_fingerprint_sha256": report.get("data", {}).get(
                    "data_fingerprint_sha256"
                ),
                "evaluation_rows": len(rows),
                "first_signal_date": rows[0]["signal_date"],
                "first_execution_date": rows[0]["target_date"],
                "last_execution_date": rows[-1]["target_date"],
            },
            "methodology": {
                "signal": (
                    "out-of-sample forecast at the feature-day close; no "
                    "same-bar execution"
                ),
                "execution": "next-session open with slippage",
                "position": "long-only, one position at a time",
                "costs": (
                    "proportional transaction cost and slippage in basis "
                    "points on entry and exit"
                ),
                "evaluation": (
                    "equity marked to each session close; final open position "
                    "liquidated at the final close when enabled"
                ),
                "risk_free_rate": active.risk_free_rate,
                "annualization_periods": active.periods_per_year,
                "buy_and_hold": (
                    "buy at first evaluation open, hold, forced liquidation at "
                    "final close"
                ),
                "persistence": (
                    "zero-return baseline abstains; it is not assigned a "
                    "fabricated directional trade"
                ),
                "data_source": "yfinance historical daily OHLCV",
            },
            "strategies": results,
            "strategy_comparison": comparison,
            "highest_simulated_return_strategy": best_return_strategy,
            "warnings": warnings,
            "limitations": [
                "A single historical path can make any strategy look good or "
                "bad by chance.",
                "The backtest uses one-step close forecasts and does not model "
                "intraday stops or limit orders.",
                "Forced liquidation at the final close is an accounting choice.",
                "No conclusion about live profitability or causality should be "
                "drawn from these simulated results.",
            ],
        }
        if write_report:
            paths = self.save_report(output, output_dir=output_dir)
            output["report_paths"] = paths
        return _json_safe(output)

    def save_report(
        self,
        report: Mapping[str, Any],
        output_dir: Optional[str] = None,
    ) -> Dict[str, str]:
        directory = output_dir or self.report_dir
        os.makedirs(directory, exist_ok=True)
        symbol = str(report.get("symbol", "symbol")).replace(".", "_")
        json_path = os.path.join(directory, f"{symbol}_backtest.json")
        trades_path = os.path.join(directory, f"{symbol}_trades.csv")
        equity_path = os.path.join(directory, f"{symbol}_equity.csv")
        comparison_path = os.path.join(
            directory, f"{symbol}_strategy_comparison.csv"
        )

        serialized = json.dumps(
            _json_safe(dict(report)),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        with open(json_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized + "\n")

        trade_fields = [
            "strategy",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "shares",
            "entry_notional",
            "exit_notional",
            "entry_cost",
            "exit_cost",
            "total_costs",
            "net_pnl",
            "net_return_pct",
            "holding_days",
            "status",
            "forced_liquidation",
        ]
        with open(trades_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=trade_fields)
            writer.writeheader()
            for strategy, strategy_report in report["strategies"].items():
                for trade in strategy_report.get("trades", []):
                    writer.writerow(
                        {
                            "strategy": strategy,
                            **{
                                field: trade.get(field)
                                for field in trade_fields
                                if field != "strategy"
                            },
                        }
                    )

        equity_fields = [
            "strategy",
            "date",
            "signal_date",
            "cash",
            "position_shares",
            "position_value",
            "equity",
            "close",
            "peak_equity",
            "drawdown",
            "drawdown_pct",
        ]
        with open(equity_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=equity_fields)
            writer.writeheader()
            for strategy, strategy_report in report["strategies"].items():
                for point in strategy_report.get("equity_curve", []):
                    writer.writerow(
                        {
                            "strategy": strategy,
                            **{
                                field: point.get(field)
                                for field in equity_fields
                                if field != "strategy"
                            },
                        }
                    )

        comparison_fields = list(
            report["strategy_comparison"][0].keys()
        ) if report.get("strategy_comparison") else []
        with open(comparison_path, "w", encoding="utf-8", newline="") as handle:
            if comparison_fields:
                writer = csv.DictWriter(
                    handle, fieldnames=comparison_fields
                )
                writer.writeheader()
                writer.writerows(report["strategy_comparison"])

        return {
            "json": json_path,
            "trades_csv": trades_path,
            "equity_csv": equity_path,
            "comparison_csv": comparison_path,
        }


backtesting_service = BacktestingService()
