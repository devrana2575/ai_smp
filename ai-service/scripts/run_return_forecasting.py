"""Run the return-vs-absolute-price experiment from the command line.

The command writes one JSON report per symbol and a combined family-level
summary CSV. It never writes to ``saved_models`` and does not change production
inference.
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

from app.services.return_forecasting_service import (  # noqa: E402
    return_forecasting_service,
)
from app.services.walk_forward_evaluation import (  # noqa: E402
    EvaluationConfig,
    walk_forward_evaluation_service,
)

FAMILY_LABELS = {
    "absolute_price": "Absolute price",
    "simple_return": "Simple return",
    "log_return": "Log return",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare absolute-price, simple-return, and log-return targets "
            "using identical chronological folds and holdout."
        )
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
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for return experiment reports",
    )
    parser.add_argument(
        "--no-write", action="store_true", help="Run without writing reports"
    )
    return parser


def _config_from_args(args: argparse.Namespace) -> EvaluationConfig:
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


def _summary_rows(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    comparison = report.get("final_holdout_comparison", {})
    rows: List[Dict[str, Any]] = []
    for row in comparison.get("rows", []):
        price = row.get("best_model_price_metrics") or {}
        returns = row.get("best_model_return_metrics") or {}
        baseline = row.get("zero_return_price_metrics") or {}
        rows.append(
            {
                "symbol": report.get("symbol"),
                "family": row.get("family"),
                "family_label": FAMILY_LABELS.get(
                    row.get("family"), row.get("family")
                ),
                "best_model_by_price_rmse": row.get(
                    "best_model_by_price_rmse"
                ),
                "price_rmse": price.get("rmse"),
                "price_mae": price.get("mae"),
                "price_nmae_pct": price.get("nmae_pct"),
                "price_nrmse_pct": price.get("nrmse_pct"),
                "return_rmse": returns.get("rmse"),
                "return_mae": returns.get("mae"),
                "return_directional_accuracy": returns.get(
                    "directional_accuracy"
                ),
                "return_signal_coverage": returns.get("signal_coverage"),
                "return_abstention_rate": returns.get("abstention_rate"),
                "zero_return_price_rmse": baseline.get("rmse"),
                "zero_return_price_mae": baseline.get("mae"),
            }
        )
    return rows


def _write_summary(rows: List[Dict[str, Any]], output_dir: str) -> Optional[str]:
    if not rows:
        return None
    path = str(Path(output_dir) / "return_forecasting_summary.csv")
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = _config_from_args(args)
    output_dir = args.output_dir or return_forecasting_service.report_dir
    rows: List[Dict[str, Any]] = []
    exit_code = 0

    for symbol in args.symbols:
        try:
            report = return_forecasting_service.evaluate_symbol(
                symbol,
                config=config,
                write_report=not args.no_write,
                output_dir=output_dir,
            )
            rows.extend(_summary_rows(report))
            comparison = report.get("final_holdout_comparison", {})
            print(
                f"{symbol}: best_price_family="
                f"{comparison.get('best_family_by_price_rmse')} "
                f"best_return_family="
                f"{comparison.get('best_family_by_return_rmse')} "
                f"zero_return_rmse="
                f"{comparison.get('absolute_family_zero_return_price_rmse')}"
            )
            if not args.no_write:
                print(f"  report: {report.get('report_path')}")
        except Exception as exc:  # noqa: BLE001 - CLI continues other symbols
            exit_code = 1
            print(f"{symbol}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)

    if rows and not args.no_write:
        path = _write_summary(rows, output_dir)
        if path:
            print(f"summary: {path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
