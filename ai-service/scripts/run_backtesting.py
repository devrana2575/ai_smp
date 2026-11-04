"""Run chronological backtests from out-of-sample walk-forward forecasts.

Run from the ``ai-service`` directory, for example::

    .\\venv\\Scripts\\python.exe -m scripts.run_backtesting TATASTEEL.NS

The command refits the walk-forward evaluation in memory, simulates the
research strategies, and writes JSON/CSV reports under ``backtesting_reports``.
It never writes to ``saved_models`` and does not change production inference.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.backtesting_service import (  # noqa: E402
    BacktestConfig,
    backtesting_service,
)
from app.services.walk_forward_evaluation import (  # noqa: E402
    EvaluationConfig,
    walk_forward_evaluation_service,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest walk-forward forecasts for one or more symbols."
    )
    parser.add_argument("symbols", nargs="+", help="Stock symbols")
    parser.add_argument("--period", default=None, help="yfinance period")
    parser.add_argument("--folds", type=int, default=None, help="Requested folds")
    parser.add_argument(
        "--holdout-fraction",
        type=float,
        default=None,
        help="Most recent chronological holdout fraction",
    )
    parser.add_argument("--model", default=None, help="Forecast model name")
    parser.add_argument(
        "--signal-source",
        choices=["selected", "ensemble"],
        default="selected",
        help="Use the development-selected model or the equal-weight ensemble",
    )
    parser.add_argument(
        "--starting-capital", type=float, default=None, help="Starting capital"
    )
    parser.add_argument(
        "--cost-bps", type=float, default=None, help="Transaction cost in bps"
    )
    parser.add_argument(
        "--slippage-bps", type=float, default=None, help="Slippage in bps"
    )
    parser.add_argument(
        "--max-allocation",
        type=float,
        default=None,
        help="Maximum fraction of cash allocated on entry (0, 1]",
    )
    parser.add_argument(
        "--buy-threshold",
        type=float,
        default=None,
        help="Predicted return threshold for entry",
    )
    parser.add_argument(
        "--sell-threshold",
        type=float,
        default=None,
        help="Predicted return threshold for exit",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for backtest reports",
    )
    parser.add_argument(
        "--no-write", action="store_true", help="Simulate without writing reports"
    )
    return parser


def _evaluation_config(args: argparse.Namespace) -> EvaluationConfig:
    base = walk_forward_evaluation_service.config
    return EvaluationConfig(
        period=args.period or base.period,
        folds=args.folds if args.folds is not None else base.folds,
        holdout_fraction=(
            args.holdout_fraction
            if args.holdout_fraction is not None
            else base.holdout_fraction
        ),
        min_train_samples=base.min_train_samples,
        min_validation_samples=base.min_validation_samples,
        min_holdout_samples=base.min_holdout_samples,
        initial_train_fraction=base.initial_train_fraction,
        selection_metric=base.selection_metric,
        random_state=base.random_state,
    )


def _backtest_config(args: argparse.Namespace) -> BacktestConfig:
    base = backtesting_service.config
    return BacktestConfig(
        starting_capital=(
            args.starting_capital
            if args.starting_capital is not None
            else base.starting_capital
        ),
        transaction_cost_bps=(
            args.cost_bps if args.cost_bps is not None else base.transaction_cost_bps
        ),
        slippage_bps=(
            args.slippage_bps
            if args.slippage_bps is not None
            else base.slippage_bps
        ),
        max_capital_allocation=(
            args.max_allocation
            if args.max_allocation is not None
            else base.max_capital_allocation
        ),
        buy_threshold=(
            args.buy_threshold
            if args.buy_threshold is not None
            else base.buy_threshold
        ),
        sell_threshold=(
            args.sell_threshold
            if args.sell_threshold is not None
            else base.sell_threshold
        ),
        risk_free_rate=base.risk_free_rate,
        periods_per_year=base.periods_per_year,
        model_name=args.model,
        signal_source=args.signal_source,
        liquidate_at_end=base.liquidate_at_end,
    )


def _write_summary(rows: List[Dict[str, Any]], output_dir: str) -> Optional[str]:
    if not rows:
        return None
    path = str(Path(output_dir) / "backtest_summary.csv")
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _summary_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for row in report.get("strategy_comparison", []):
        rows.append(
            {
                "symbol": report.get("symbol"),
                "model": report.get("model", {}).get("name"),
                "strategy": row.get("strategy"),
                "final_equity": row.get("final_equity"),
                "total_return_pct": row.get("total_return_pct"),
                "annualized_return_pct": row.get("annualized_return_pct"),
                "annualized_volatility_pct": row.get(
                    "annualized_volatility_pct"
                ),
                "sharpe_ratio": row.get("sharpe_ratio"),
                "sortino_ratio": row.get("sortino_ratio"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "calmar_ratio": row.get("calmar_ratio"),
                "closed_trades": row.get("closed_trades"),
                "win_rate_pct": row.get("win_rate_pct"),
                "profit_factor": row.get("profit_factor"),
                "transaction_costs": row.get("transaction_costs"),
            }
        )
    return rows


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    evaluation_config = _evaluation_config(args)
    backtest_config = _backtest_config(args)
    output_dir = args.output_dir or backtesting_service.report_dir
    exit_code = 0
    summary_rows: List[Dict[str, Any]] = []

    for symbol in args.symbols:
        try:
            evaluation_report = walk_forward_evaluation_service.evaluate_symbol(
                symbol,
                config=evaluation_config,
                write_report=False,
            )
            report = backtesting_service.run_symbol(
                symbol,
                config=backtest_config,
                evaluation_report=evaluation_report,
                write_report=not args.no_write,
                output_dir=output_dir,
            )
            summary_rows.extend(_summary_rows(report))
            print(
                f"{symbol}: model={report['model']['name']} "
                f"rows={report['data']['evaluation_rows']} "
                f"highest_simulated_return="
                f"{report['highest_simulated_return_strategy']} "
                f"buy_hold_return="
                f"{report['strategies']['buy_and_hold']['equity_metrics']['total_return_pct']} "
                f"cash_return="
                f"{report['strategies']['cash']['equity_metrics']['total_return_pct']}"
            )
            if not args.no_write:
                print(f"  report: {report['report_paths']['json']}")
        except Exception as exc:  # noqa: BLE001 - CLI continues other symbols
            exit_code = 1
            print(
                f"{symbol}: ERROR {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )

    if summary_rows and not args.no_write:
        path = _write_summary(summary_rows, output_dir)
        if path:
            print(f"summary: {path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
