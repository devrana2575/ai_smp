import csv
import json

import pytest

from app.services.backtesting_service import (
    STRATEGY_CASH,
    STRATEGY_NAMES,
    STRATEGY_PERSISTENCE,
    BacktestConfig,
    BacktestingService,
)


def _validation(dates, targets, current, opens, closes, predictions):
    return {
        "dates": dates,
        "target_dates": targets,
        "current_close": current,
        "actual_next_open": opens,
        "actual_next_close": closes,
        "predictions": {"linear_regression": predictions},
    }


@pytest.fixture
def fake_report():
    first = _validation(
        dates=["2025-01-02", "2025-01-03", "2025-01-06"],
        targets=["2025-01-03", "2025-01-06", "2025-01-07"],
        current=[100.0, 101.0, 102.0],
        opens=[100.5, 101.5, 102.5],
        closes=[101.0, 102.0, 103.0],
        predictions=[102.0, 103.0, 101.0],
    )
    holdout = _validation(
        dates=["2025-01-07", "2025-01-08"],
        targets=["2025-01-08", "2025-01-09"],
        current=[103.0, 104.0],
        opens=[103.5, 104.5],
        closes=[104.0, 105.0],
        predictions=[105.0, 103.0],
    )
    return {
        "symbol": "TEST.NS",
        "data": {
            "period": "2y",
            "data_fingerprint_sha256": "abc123",
        },
        "best_performing_model": {"selected_model": "linear_regression"},
        "development_validation": {
            "folds": [{"status": "ok", "validation": first}]
        },
        "final_holdout": {"validation": holdout},
    }


def test_simulate_buy_and_hold_and_costs(fake_report):
    service = BacktestingService()
    rows = service.extract_rows(fake_report, "linear_regression")
    assert len(rows) == 5
    assert [row["target_date"] for row in rows] == sorted(
        row["target_date"] for row in rows
    )

    result = service.simulate_strategy(rows, "buy_and_hold")
    assert result["status"] == "ok"
    assert result["equity_metrics"]["final_equity"] > 0
    assert result["trade_metrics"]["closed_trades"] == 1
    assert result["trades"][0]["forced_liquidation"] is True
    assert result["trades"][0]["total_costs"] > 0
    assert result["equity_curve"][-1]["forced_liquidation"] is True
    assert result["equity_curve"][-1]["position_shares"] == 0.0


def test_simulate_cash_and_persistence_abstain(fake_report):
    service = BacktestingService()
    rows = service.extract_rows(fake_report, "linear_regression")

    cash = service.simulate_strategy(rows, STRATEGY_CASH)
    assert cash["trade_metrics"]["closed_trades"] == 0
    assert cash["equity_metrics"]["total_return_pct"] == 0.0

    persistence = service.simulate_strategy(rows, STRATEGY_PERSISTENCE)
    assert persistence["trade_metrics"]["closed_trades"] == 0
    assert persistence["equity_metrics"]["total_return_pct"] == 0.0
    assert any("abstain" in warning for warning in persistence["warnings"])


def test_model_and_threshold_strategies_trade(fake_report):
    config = BacktestConfig(
        starting_capital=100000.0,
        transaction_cost_bps=5.0,
        slippage_bps=5.0,
        max_capital_allocation=0.5,
        buy_threshold=0.005,
        sell_threshold=-0.005,
        liquidate_at_end=True,
    )
    service = BacktestingService(config=config)
    rows = service.extract_rows(fake_report, "linear_regression")

    model = service.simulate_strategy(rows, "model_directional")
    threshold = service.simulate_strategy(rows, "threshold")
    assert model["trade_metrics"]["total_trades"] >= 1
    assert threshold["trade_metrics"]["total_trades"] >= 1
    assert model["equity_metrics"]["final_equity"] != pytest.approx(
        100000.0
    )


def test_run_symbol_writes_reports(fake_report, tmp_path):
    service = BacktestingService(report_dir=str(tmp_path))
    config = BacktestConfig(starting_capital=100000.0)
    report = service.run_symbol(
        "TEST.NS",
        config=config,
        evaluation_report=fake_report,
        write_report=True,
    )

    assert report["status"] == "completed"
    assert report["production_inference_changed"] is False
    assert set(report["strategies"]) == set(STRATEGY_NAMES)
    assert len(report["strategy_comparison"]) == len(STRATEGY_NAMES)
    assert report["report_paths"]["json"].endswith("_backtest.json")

    with open(report["report_paths"]["json"], encoding="utf-8") as handle:
        saved = json.load(handle)
    assert saved["symbol"] == "TEST.NS"

    with open(
        report["report_paths"]["trades_csv"], encoding="utf-8", newline=""
    ) as handle:
        trade_rows = list(csv.DictReader(handle))
    assert len(trade_rows) >= 1

    with open(
        report["report_paths"]["comparison_csv"],
        encoding="utf-8",
        newline="",
    ) as handle:
        comparison_rows = list(csv.DictReader(handle))
    assert len(comparison_rows) == len(STRATEGY_NAMES)


def test_extract_rejects_duplicate_target_dates(fake_report):
    service = BacktestingService()
    duplicate = json.loads(json.dumps(fake_report))
    duplicate["final_holdout"]["validation"]["target_dates"][0] = (
        duplicate["development_validation"]["folds"][0]["validation"][
            "target_dates"
        ][0]
    )
    with pytest.raises(ValueError, match="duplicates"):
        service.extract_rows(duplicate, "linear_regression")
