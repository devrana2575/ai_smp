import pytest

from app.services.risk_metrics_service import (
    calculate_equity_metrics,
    calculate_trade_metrics,
    compare_strategies,
    drawdown_series,
    monthly_returns,
)


def test_equity_metrics_known_path():
    curve = [
        {"date": "2025-01-02", "equity": 110.0},
        {"date": "2025-01-03", "equity": 99.0},
        {"date": "2025-01-06", "equity": 120.0},
    ]
    metrics = calculate_equity_metrics(
        curve, starting_capital=100.0, periods_per_year=252
    )

    assert metrics["final_equity"] == 120.0
    assert metrics["total_return_pct"] == pytest.approx(20.0)
    assert metrics["max_drawdown_pct"] == pytest.approx(-10.0)
    assert metrics["n_periods"] == 3
    assert metrics["annualized_volatility_pct"] is not None
    assert metrics["sharpe_ratio"] is not None
    assert metrics["sortino_ratio"] is not None

    drawdowns = drawdown_series(curve)
    assert drawdowns[1]["drawdown_pct"] == pytest.approx(-10.0)
    assert drawdowns[2]["drawdown_pct"] == pytest.approx(0.0)


def test_equity_metrics_cash_and_empty():
    cash = calculate_equity_metrics(
        [
            {"date": "2025-01-02", "equity": 100.0},
            {"date": "2025-01-03", "equity": 100.0},
        ],
        starting_capital=100.0,
    )
    assert cash["total_return_pct"] == 0.0
    assert cash["max_drawdown_pct"] == 0.0
    assert cash["sharpe_ratio"] is None

    empty = calculate_equity_metrics([], starting_capital=100.0)
    assert empty["final_equity"] is None
    assert empty["total_return_pct"] is None


def test_trade_metrics_excludes_open_trades_from_win_rate():
    trades = [
        {
            "status": "closed",
            "net_pnl": 10.0,
            "entry_notional": 100.0,
            "total_costs": 1.0,
            "holding_days": 3,
        },
        {
            "status": "closed",
            "net_pnl": -5.0,
            "entry_notional": 100.0,
            "total_costs": 1.0,
            "holding_days": 2,
        },
        {
            "status": "open",
            "net_pnl": 50.0,
            "entry_notional": 100.0,
            "total_costs": 0.5,
            "holding_days": 4,
        },
    ]
    metrics = calculate_trade_metrics(trades)

    assert metrics["closed_trades"] == 2
    assert metrics["open_trades"] == 1
    assert metrics["win_rate_pct"] == 50.0
    assert metrics["profit_factor"] == 2.0
    assert metrics["average_trade_return_pct"] == pytest.approx(2.5)
    assert metrics["average_holding_days"] == 2.5


def test_monthly_returns_and_strategy_comparison():
    curve = [
        {"date": "2025-01-02", "equity": 100.0},
        {"date": "2025-01-31", "equity": 110.0},
        {"date": "2025-02-03", "equity": 121.0},
    ]
    months = monthly_returns(curve)
    assert [row["month"] for row in months] == ["2025-01", "2025-02"]
    assert months[0]["return_pct"] == pytest.approx(10.0)
    assert months[1]["return_pct"] == pytest.approx(10.0)

    comparison = compare_strategies(
        {
            "buy_and_hold": {
                "label": "Buy and Hold",
                "equity_metrics": {
                    "final_equity": 121.0,
                    "total_return_pct": 21.0,
                    "max_drawdown_pct": -10.0,
                },
                "trade_metrics": {"closed_trades": 1},
            },
            "cash": {
                "label": "Cash",
                "equity_metrics": {
                    "final_equity": 100.0,
                    "total_return_pct": 0.0,
                    "max_drawdown_pct": 0.0,
                },
                "trade_metrics": {"closed_trades": 0},
            },
        }
    )
    assert comparison[1]["excess_return_vs_buy_and_hold_pp"] == -21.0
    assert comparison[1]["drawdown_difference_vs_buy_and_hold_pp"] == 10.0
