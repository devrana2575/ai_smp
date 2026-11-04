"""Risk and performance metrics for simulated strategy equity curves.

All functions are pure and independent of market data infrastructure. Returns
are fractions internally and are converted to percentages in report fields
where the name says ``pct``. No metric here is a guarantee of future
performance.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


def _round(value: Optional[float], digits: int = 6) -> Optional[float]:
    if value is None:
        return None
    value = float(value)
    if not math.isfinite(value):
        return None
    return round(value, digits)


def _finite_returns(
    equity_curve: Sequence[Mapping[str, Any]],
    starting_capital: float,
) -> List[float]:
    equities = [float(point["equity"]) for point in equity_curve]
    if not equities:
        return []
    returns: List[float] = []
    previous = float(starting_capital)
    for equity in equities:
        if previous == 0:
            returns.append(0.0)
        else:
            returns.append(equity / previous - 1.0)
        previous = equity
    return returns


def drawdown_series(
    equity_curve: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Return running peak and drawdown (fraction and percent) per point."""

    peak: Optional[float] = None
    output: List[Dict[str, Any]] = []
    for point in equity_curve:
        equity = float(point["equity"])
        peak = equity if peak is None else max(peak, equity)
        drawdown = 0.0 if peak == 0 else equity / peak - 1.0
        output.append(
            {
                "date": point.get("date"),
                "equity": _round(equity),
                "peak_equity": _round(peak),
                "drawdown": _round(drawdown),
                "drawdown_pct": _round(drawdown * 100.0),
            }
        )
    return output


def calculate_equity_metrics(
    equity_curve: Sequence[Mapping[str, Any]],
    starting_capital: float,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> Dict[str, Any]:
    """Calculate return, volatility, drawdown, and risk-adjusted metrics."""

    if starting_capital <= 0:
        raise ValueError("starting_capital must be positive")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    if not equity_curve:
        return {
            "n_periods": 0,
            "starting_capital": _round(starting_capital),
            "final_equity": None,
            "total_return_pct": None,
            "annualized_return_pct": None,
            "annualized_volatility_pct": None,
            "sharpe_ratio": None,
            "sortino_ratio": None,
            "max_drawdown_pct": None,
            "calmar_ratio": None,
            "best_period_return_pct": None,
            "worst_period_return_pct": None,
        }

    returns = _finite_returns(equity_curve, starting_capital)
    final_equity = float(equity_curve[-1]["equity"])
    total_return = final_equity / starting_capital - 1.0
    n_periods = len(returns)

    annualized_return: Optional[float] = None
    if n_periods > 0 and total_return > -1.0:
        annualized_return = (
            (1.0 + total_return) ** (periods_per_year / n_periods) - 1.0
        )

    if n_periods > 1:
        mean_return = sum(returns) / n_periods
        variance = sum((value - mean_return) ** 2 for value in returns) / (
            n_periods - 1
        )
        volatility = math.sqrt(max(variance, 0.0))
    else:
        mean_return = returns[0] if returns else 0.0
        volatility = 0.0

    annualized_volatility = volatility * math.sqrt(periods_per_year)
    rf_period = (1.0 + risk_free_rate) ** (1.0 / periods_per_year) - 1.0
    excess = [value - rf_period for value in returns]

    sharpe: Optional[float] = None
    if volatility > 0:
        sharpe = (sum(excess) / len(excess)) / volatility * math.sqrt(
            periods_per_year
        )

    downside_squares = [min(value, 0.0) ** 2 for value in excess]
    downside_deviation = (
        math.sqrt(sum(downside_squares) / len(downside_squares))
        if downside_squares
        else 0.0
    )
    sortino: Optional[float] = None
    if downside_deviation > 0:
        sortino = (
            (sum(excess) / len(excess))
            / downside_deviation
            * math.sqrt(periods_per_year)
        )

    peak: Optional[float] = None
    max_drawdown = 0.0
    for point in equity_curve:
        equity = float(point["equity"])
        peak = equity if peak is None else max(peak, equity)
        if peak and peak != 0:
            max_drawdown = min(max_drawdown, equity / peak - 1.0)

    calmar: Optional[float] = None
    if max_drawdown < 0 and annualized_return is not None:
        calmar = annualized_return / abs(max_drawdown)

    return {
        "n_periods": n_periods,
        "starting_capital": _round(starting_capital),
        "final_equity": _round(final_equity),
        "total_return_pct": _round(total_return * 100.0),
        "annualized_return_pct": _round(
            annualized_return * 100.0 if annualized_return is not None else None
        ),
        "annualized_volatility_pct": _round(
            annualized_volatility * 100.0
        ),
        "mean_period_return_pct": _round(mean_return * 100.0),
        "sharpe_ratio": _round(sharpe),
        "sortino_ratio": _round(sortino),
        "max_drawdown_pct": _round(max_drawdown * 100.0),
        "calmar_ratio": _round(calmar),
        "best_period_return_pct": _round(max(returns) * 100.0),
        "worst_period_return_pct": _round(min(returns) * 100.0),
        "risk_free_rate": _round(risk_free_rate),
        "periods_per_year": int(periods_per_year),
    }


def calculate_trade_metrics(
    trades: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Summarize closed trades. Open trades are reported separately."""

    trades = list(trades)
    closed = [
        trade for trade in trades if trade.get("status") == "closed"
    ]
    open_trades = [
        trade for trade in trades if trade.get("status") == "open"
    ]
    net_returns = [
        float(trade["net_pnl"]) / float(trade["entry_notional"])
        for trade in closed
        if trade.get("entry_notional")
    ]
    net_pnls = [float(trade["net_pnl"]) for trade in closed]
    wins = [value for value in net_pnls if value > 0]
    losses = [value for value in net_pnls if value < 0]
    holding_days = [
        float(trade["holding_days"])
        for trade in closed
        if trade.get("holding_days") is not None
    ]

    profit_factor: Optional[float] = None
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = None  # Undefined/infinite; do not report a fake number.

    return {
        "total_trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": len(open_trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": _round(
            len(wins) / len(closed) * 100.0 if closed else None
        ),
        "gross_profit": _round(gross_profit),
        "gross_loss": _round(-gross_loss),
        "net_profit": _round(sum(net_pnls)),
        "profit_factor": _round(profit_factor),
        "average_trade_return_pct": _round(
            sum(net_returns) / len(net_returns) * 100.0
            if net_returns
            else None
        ),
        "average_win_pct": _round(
            sum(value for value in net_returns if value > 0)
            / len([value for value in net_returns if value > 0])
            * 100.0
            if any(value > 0 for value in net_returns)
            else None
        ),
        "average_loss_pct": _round(
            sum(value for value in net_returns if value < 0)
            / len([value for value in net_returns if value < 0])
            * 100.0
            if any(value < 0 for value in net_returns)
            else None
        ),
        "average_holding_days": _round(
            sum(holding_days) / len(holding_days) if holding_days else None
        ),
        "total_transaction_costs": _round(
            sum(float(trade.get("total_costs", 0.0)) for trade in trades)
        ),
        "note": (
            "Open trades are marked to market in the equity curve but are not "
            "included in win rate, profit factor, or average closed-trade "
            "return. An unclosed profitable trade does not receive a fabricated "
            "win rate."
        ),
    }


def monthly_returns(
    equity_curve: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Aggregate equity-curve returns by calendar month."""

    if not equity_curve:
        return []
    output: List[Dict[str, Any]] = []
    month_key: Optional[str] = None
    month_start_equity: Optional[float] = None
    previous_equity: Optional[float] = None
    for point in equity_curve:
        date = str(point.get("date") or "")
        key = date[:7]
        equity = float(point["equity"])
        if key != month_key:
            if month_key is not None and month_start_equity is not None:
                month_return = (
                    previous_equity / month_start_equity - 1.0
                    if previous_equity is not None and month_start_equity
                    else 0.0
                )
                output.append(
                    {
                        "month": month_key,
                        "return_pct": _round(month_return * 100.0),
                    }
                )
            month_key = key
            month_start_equity = previous_equity if previous_equity else equity
        previous_equity = equity
    if month_key is not None and month_start_equity is not None:
        month_return = (
            previous_equity / month_start_equity - 1.0
            if previous_equity is not None and month_start_equity
            else 0.0
        )
        output.append(
            {"month": month_key, "return_pct": _round(month_return * 100.0)}
        )
    return output


def compare_strategies(
    results: Mapping[str, Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Build a comparison table using already-computed strategy results."""

    rows: List[Dict[str, Any]] = []
    benchmark = results.get("buy_and_hold", {}).get("equity_metrics", {})
    for name, result in results.items():
        equity = result.get("equity_metrics", {})
        trades = result.get("trade_metrics", {})
        total_return = equity.get("total_return_pct")
        benchmark_return = benchmark.get("total_return_pct")
        excess: Optional[float] = None
        if total_return is not None and benchmark_return is not None:
            excess = float(total_return) - float(benchmark_return)
        max_drawdown = equity.get("max_drawdown_pct")
        benchmark_drawdown = benchmark.get("max_drawdown_pct")
        drawdown_difference: Optional[float] = None
        if max_drawdown is not None and benchmark_drawdown is not None:
            drawdown_difference = float(max_drawdown) - float(
                benchmark_drawdown
            )
        rows.append(
            {
                "strategy": name,
                "label": result.get("label", name),
                "final_equity": equity.get("final_equity"),
                "total_return_pct": total_return,
                "annualized_return_pct": equity.get(
                    "annualized_return_pct"
                ),
                "annualized_volatility_pct": equity.get(
                    "annualized_volatility_pct"
                ),
                "sharpe_ratio": equity.get("sharpe_ratio"),
                "sortino_ratio": equity.get("sortino_ratio"),
                "max_drawdown_pct": max_drawdown,
                "calmar_ratio": equity.get("calmar_ratio"),
                "closed_trades": trades.get("closed_trades"),
                "win_rate_pct": trades.get("win_rate_pct"),
                "profit_factor": trades.get("profit_factor"),
                "transaction_costs": trades.get("total_transaction_costs"),
                "excess_return_vs_buy_and_hold_pp": _round(excess),
                "drawdown_difference_vs_buy_and_hold_pp": _round(
                    drawdown_difference
                ),
            }
        )
    return rows
