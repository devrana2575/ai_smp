"""Run chronological walk-forward evaluation from the command line.

Run from the ``ai-service`` directory, for example::

    .\\venv\\Scripts\\python.exe -m scripts.run_walk_forward_evaluation TATASTEEL.NS

The command writes one JSON report per symbol plus a combined summary CSV.
It never writes to ``saved_models`` and does not change production inference.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow ``python scripts/run_walk_forward_evaluation.py`` as well as
# ``python -m scripts.run_walk_forward_evaluation``.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.walk_forward_evaluation import (  # noqa: E402
    EvaluationConfig,
    walk_forward_evaluation_service,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run expanding-window walk-forward evaluation for one or more "
            "stock symbols."
        )
    )
    parser.add_argument(
        "symbols",
        nargs="+",
        help="Stock symbols, for example TATASTEEL.NS",
    )
    parser.add_argument("--period", default=None, help="yfinance period (default: 2y)")
    parser.add_argument("--folds", type=int, default=None, help="Requested folds")
    parser.add_argument(
        "--holdout-fraction",
        type=float,
        default=None,
        help="Most recent chronological fraction reserved as final holdout",
    )
    parser.add_argument(
        "--min-train-samples",
        type=int,
        default=None,
        help="Minimum training rows per fold",
    )
    parser.add_argument(
        "--min-validation-samples",
        type=int,
        default=None,
        help="Minimum validation rows per fold",
    )
    parser.add_argument(
        "--min-holdout-samples",
        type=int,
        default=None,
        help="Minimum final-holdout rows",
    )
    parser.add_argument(
        "--initial-train-fraction",
        type=float,
        default=None,
        help="Initial development fraction used for the first training window",
    )
    parser.add_argument(
        "--selection-metric",
        choices=["rmse", "mae"],
        default=None,
        help="Primary development selection metric",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for JSON reports and summary CSV",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Evaluate without writing report files",
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
        min_train_samples=(
            args.min_train_samples
            if args.min_train_samples is not None
            else base.min_train_samples
        ),
        min_validation_samples=(
            args.min_validation_samples
            if args.min_validation_samples is not None
            else base.min_validation_samples
        ),
        min_holdout_samples=(
            args.min_holdout_samples
            if args.min_holdout_samples is not None
            else base.min_holdout_samples
        ),
        initial_train_fraction=(
            args.initial_train_fraction
            if args.initial_train_fraction is not None
            else base.initial_train_fraction
        ),
        selection_metric=args.selection_metric or base.selection_metric,
        random_state=base.random_state,
    )


def _metric_value(report: Dict[str, Any], *path: str) -> Optional[float]:
    value: Any = report
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summary_row(report: Dict[str, Any]) -> Dict[str, Any]:
    selected = report.get("best_performing_model", {}).get("selected_model")
    development = report.get("development_validation", {}).get("aggregated", {})
    holdout = report.get("final_holdout", {}).get("models", {})
    baseline_name = report.get("baseline_comparison", {}).get(
        "baseline_name", "naive_persistence"
    )
    ensemble_name = report.get("ensemble_evaluation", {}).get(
        "name", "ensemble_equal_weight"
    )

    def metrics_for(source: Dict[str, Any], name: Optional[str]) -> Dict[str, Any]:
        if not name:
            return {}
        entry = source.get(name, {})
        return entry.get("metrics", {}) if isinstance(entry, dict) else {}

    def dev_metrics(name: Optional[str]) -> Dict[str, Any]:
        if not name:
            return {}
        entry = development.get(name, {})
        return entry.get("metrics", {}) if isinstance(entry, dict) else {}

    selected_dev = dev_metrics(selected)
    selected_holdout = metrics_for(holdout, selected)
    baseline_dev = dev_metrics(baseline_name)
    baseline_holdout = metrics_for(holdout, baseline_name)
    ensemble_dev = dev_metrics(ensemble_name)
    ensemble_holdout = metrics_for(holdout, ensemble_name)

    fold_generation = report.get("development_validation", {}).get(
        "fold_generation", {}
    )
    holdout_split = report.get("data", {}).get("holdout_split", {})

    return {
        "symbol": report.get("symbol"),
        "period": report.get("config", {}).get("period"),
        "selected_model": selected,
        "folds_used": fold_generation.get("folds_used"),
        "development_rows": fold_generation.get("development_rows"),
        "holdout_rows": holdout_split.get("holdout_rows"),
        "selected_dev_mae": selected_dev.get("mae"),
        "selected_dev_rmse": selected_dev.get("rmse"),
        "selected_dev_r2": selected_dev.get("r2_score"),
        "selected_dev_smape": selected_dev.get("smape"),
        "selected_dev_directional_accuracy": selected_dev.get(
            "directional_accuracy"
        ),
        "selected_dev_signal_coverage": selected_dev.get("signal_coverage"),
        "selected_dev_abstention_rate": selected_dev.get("abstention_rate"),
        "selected_dev_nmae_pct": selected_dev.get("nmae_pct"),
        "selected_dev_nrmse_pct": selected_dev.get("nrmse_pct"),
        "selected_dev_mase_vs_random_walk": selected_dev.get(
            "mase_vs_random_walk"
        ),
        "baseline_dev_mae": baseline_dev.get("mae"),
        "baseline_dev_rmse": baseline_dev.get("rmse"),
        "baseline_dev_r2": baseline_dev.get("r2_score"),
        "baseline_dev_smape": baseline_dev.get("smape"),
        "baseline_dev_directional_accuracy": baseline_dev.get(
            "directional_accuracy"
        ),
        "baseline_dev_signal_coverage": baseline_dev.get("signal_coverage"),
        "baseline_dev_abstention_rate": baseline_dev.get("abstention_rate"),
        "baseline_dev_nmae_pct": baseline_dev.get("nmae_pct"),
        "baseline_dev_nrmse_pct": baseline_dev.get("nrmse_pct"),
        "baseline_dev_mase_vs_random_walk": baseline_dev.get(
            "mase_vs_random_walk"
        ),
        "ensemble_dev_mae": ensemble_dev.get("mae"),
        "ensemble_dev_rmse": ensemble_dev.get("rmse"),
        "ensemble_dev_r2": ensemble_dev.get("r2_score"),
        "ensemble_dev_smape": ensemble_dev.get("smape"),
        "ensemble_dev_directional_accuracy": ensemble_dev.get(
            "directional_accuracy"
        ),
        "ensemble_dev_signal_coverage": ensemble_dev.get("signal_coverage"),
        "ensemble_dev_abstention_rate": ensemble_dev.get("abstention_rate"),
        "ensemble_dev_nmae_pct": ensemble_dev.get("nmae_pct"),
        "ensemble_dev_nrmse_pct": ensemble_dev.get("nrmse_pct"),
        "ensemble_dev_mase_vs_random_walk": ensemble_dev.get(
            "mase_vs_random_walk"
        ),
        "selected_holdout_mae": selected_holdout.get("mae"),
        "selected_holdout_rmse": selected_holdout.get("rmse"),
        "selected_holdout_r2": selected_holdout.get("r2_score"),
        "selected_holdout_smape": selected_holdout.get("smape"),
        "selected_holdout_directional_accuracy": selected_holdout.get(
            "directional_accuracy"
        ),
        "selected_holdout_signal_coverage": selected_holdout.get(
            "signal_coverage"
        ),
        "selected_holdout_abstention_rate": selected_holdout.get(
            "abstention_rate"
        ),
        "selected_holdout_nmae_pct": selected_holdout.get("nmae_pct"),
        "selected_holdout_nrmse_pct": selected_holdout.get("nrmse_pct"),
        "selected_holdout_mase_vs_random_walk": selected_holdout.get(
            "mase_vs_random_walk"
        ),
        "baseline_holdout_mae": baseline_holdout.get("mae"),
        "baseline_holdout_rmse": baseline_holdout.get("rmse"),
        "baseline_holdout_r2": baseline_holdout.get("r2_score"),
        "baseline_holdout_smape": baseline_holdout.get("smape"),
        "baseline_holdout_directional_accuracy": baseline_holdout.get(
            "directional_accuracy"
        ),
        "baseline_holdout_signal_coverage": baseline_holdout.get(
            "signal_coverage"
        ),
        "baseline_holdout_abstention_rate": baseline_holdout.get(
            "abstention_rate"
        ),
        "baseline_holdout_nmae_pct": baseline_holdout.get("nmae_pct"),
        "baseline_holdout_nrmse_pct": baseline_holdout.get("nrmse_pct"),
        "baseline_holdout_mase_vs_random_walk": baseline_holdout.get(
            "mase_vs_random_walk"
        ),
        "ensemble_holdout_mae": ensemble_holdout.get("mae"),
        "ensemble_holdout_rmse": ensemble_holdout.get("rmse"),
        "ensemble_holdout_r2": ensemble_holdout.get("r2_score"),
        "ensemble_holdout_smape": ensemble_holdout.get("smape"),
        "ensemble_holdout_directional_accuracy": ensemble_holdout.get(
            "directional_accuracy"
        ),
        "ensemble_holdout_signal_coverage": ensemble_holdout.get(
            "signal_coverage"
        ),
        "ensemble_holdout_abstention_rate": ensemble_holdout.get(
            "abstention_rate"
        ),
        "ensemble_holdout_nmae_pct": ensemble_holdout.get("nmae_pct"),
        "ensemble_holdout_nrmse_pct": ensemble_holdout.get("nrmse_pct"),
        "ensemble_holdout_mase_vs_random_walk": ensemble_holdout.get(
            "mase_vs_random_walk"
        ),
        "ensemble_beats_baseline_development": report.get(
            "ensemble_evaluation", {}
        ).get("beats_baseline_development_rmse"),
        "ensemble_beats_baseline_holdout": report.get(
            "ensemble_evaluation", {}
        ).get("beats_baseline_final_holdout_rmse"),
    }


def _write_summary_csv(rows: List[Dict[str, Any]], output_dir: str) -> str:
    path = str(Path(output_dir) / "walk_forward_summary.csv")
    if not rows:
        return path
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

    output_dir = args.output_dir or walk_forward_evaluation_service.report_dir
    rows: List[Dict[str, Any]] = []
    exit_code = 0

    for symbol in args.symbols:
        try:
            report = walk_forward_evaluation_service.evaluate_symbol(
                symbol,
                config=config,
                write_report=not args.no_write,
                output_dir=output_dir,
            )
            row = _summary_row(report)
            rows.append(row)
            selected = row["selected_model"]
            print(
                f"{symbol}: folds={row['folds_used']} "
                f"selected={selected} "
                f"dev_rmse={row['selected_dev_rmse']} "
                f"baseline_dev_rmse={row['baseline_dev_rmse']} "
                f"ensemble_dev_rmse={row['ensemble_dev_rmse']} "
                f"holdout_rmse={row['selected_holdout_rmse']} "
                f"baseline_holdout_rmse={row['baseline_holdout_rmse']} "
                f"ensemble_holdout_rmse={row['ensemble_holdout_rmse']} "
                f"ensemble_beats_baseline_dev="
                f"{row['ensemble_beats_baseline_development']} "
                f"ensemble_beats_baseline_holdout="
                f"{row['ensemble_beats_baseline_holdout']}"
            )
            if not args.no_write:
                print(f"  report: {report.get('report_path')}")
        except Exception as exc:  # noqa: BLE001 - CLI continues other symbols
            exit_code = 1
            print(f"{symbol}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)

    if rows and not args.no_write:
        summary_path = _write_summary_csv(rows, output_dir)
        print(f"summary: {summary_path}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
