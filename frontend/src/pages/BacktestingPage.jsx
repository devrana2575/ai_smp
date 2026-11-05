import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import toast from "react-hot-toast";
import { useAuth } from "../context/AuthContext";
import { researchService, errorMessage } from "../services/researchService";
import {
  EmptyState,
  JobNotice,
  MetricCard,
  ResearchHeader,
  Section,
  SimpleTable,
  StatusBadge,
  SymbolPicker,
  WarningList,
  formatDate,
  formatNumber,
  formatPct,
  modelLabel,
} from "../components/research/ResearchUi";

const STRATEGY_LABELS = {
  buy_and_hold: "Buy and hold",
  cash: "Cash",
  persistence: "Persistence",
  model_directional: "Model directional",
  threshold: "Threshold",
};

const defaultOptions = {
  starting_capital: 100000,
  transaction_cost_bps: 5,
  slippage_bps: 5,
  max_capital_allocation: 1,
  buy_threshold: 0.005,
  sell_threshold: -0.005,
  signal_source: "selected",
  model: "",
  folds: 5,
  holdout_fraction: 0.2,
};

const numberOrUndefined = (value) => {
  if (value === "" || value === null || value === undefined) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const BacktestingPage = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [searchParams] = useSearchParams();
  const [symbol, setSymbol] = useState(
    searchParams.get("symbol") || "TATASTEEL.NS"
  );
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [selectedStrategy, setSelectedStrategy] = useState("model_directional");
  const [options, setOptions] = useState(defaultOptions);

  useEffect(() => {
    if (!symbol) return;
    loadLatest();
  }, [symbol]);

  const loadLatest = async () => {
    setError("");
    setJob(null);
    try {
      const data = await researchService.latestBacktest(symbol);
      setReport(data);
      if (data.config) {
        setOptions((current) => ({
          ...current,
          starting_capital: data.config.starting_capital ?? current.starting_capital,
          transaction_cost_bps: data.config.transaction_cost_bps ?? current.transaction_cost_bps,
          slippage_bps: data.config.slippage_bps ?? current.slippage_bps,
          max_capital_allocation: data.config.max_capital_allocation ?? current.max_capital_allocation,
          buy_threshold: data.config.buy_threshold ?? current.buy_threshold,
          sell_threshold: data.config.sell_threshold ?? current.sell_threshold,
          signal_source: data.config.signal_source ?? current.signal_source,
          model: data.config.model_name || "",
        }));
      }
    } catch (err) {
      if (err?.response?.status === 404) setReport(null);
      else setError(errorMessage(err, "Failed to load the backtest report"));
    }
  };

  const updateOption = (key, value) =>
    setOptions((current) => ({ ...current, [key]: value }));

  const runBacktest = async () => {
    setLoading(true);
    setError("");
    try {
      const payload = {
        folds: numberOrUndefined(options.folds),
        holdout_fraction: numberOrUndefined(options.holdout_fraction),
        model: options.model || undefined,
        signal_source: options.signal_source,
        starting_capital: numberOrUndefined(options.starting_capital),
        transaction_cost_bps: numberOrUndefined(options.transaction_cost_bps),
        slippage_bps: numberOrUndefined(options.slippage_bps),
        max_capital_allocation: numberOrUndefined(options.max_capital_allocation),
        buy_threshold: numberOrUndefined(options.buy_threshold),
        sell_threshold: numberOrUndefined(options.sell_threshold),
      };
      const response = await researchService.runBacktest(symbol, payload);
      setJob(response.job);
      const completed = await researchService.waitForJob(response.job.job_id, {
        onUpdate: setJob,
      });
      setJob(completed);
      if (completed.result) setReport(completed.result);
      else await loadLatest();
      toast.success("Backtest completed");
    } catch (err) {
      setError(errorMessage(err, "Backtest failed"));
      toast.error("Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  const strategies = report?.strategies || {};
  const comparison = report?.strategy_comparison || [];
  const strategy = strategies[selectedStrategy] || strategies.model_directional;
  const buyHold = strategies.buy_and_hold;
  const equityChart = useMemo(() => {
    if (!strategy?.equity_curve) return [];
    const buyHoldByDate = new Map(
      (buyHold?.equity_curve || []).map((point) => [point.date, point.equity])
    );
    return strategy.equity_curve.map((point) => ({
      date: point.date,
      selected: point.equity,
      buyHold: buyHoldByDate.get(point.date) ?? null,
    }));
  }, [strategy, buyHold]);
  const drawdownChart = (strategy?.equity_curve || []).map((point) => ({
    date: point.date,
    drawdown: point.drawdown_pct,
  }));
  const tradeRows = (strategy?.trades || []).slice(0, 200);
  const metrics = strategy?.equity_metrics || {};

  return (
    <div className="space-y-6">
      <ResearchHeader
        title="Backtesting laboratory"
        description="Simulate long-only strategies from out-of-sample walk-forward forecasts. Signals form at the feature-day close and execute at the next session open with proportional costs and slippage."
        onRefresh={loadLatest}
        onRun={runBacktest}
        runLabel="Run backtest"
        loading={loading}
        canRun={isAdmin && Boolean(symbol)}
      />

      <div className="bg-white rounded-xl shadow-md p-5 space-y-5">
        <SymbolPicker value={symbol} onChange={setSymbol} disabled={loading} />
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Simulation assumptions</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            {[
              ["starting_capital", "Starting capital", "number", "100000"],
              ["transaction_cost_bps", "Transaction cost (bps)", "number", "5"],
              ["slippage_bps", "Slippage (bps)", "number", "5"],
              ["max_capital_allocation", "Maximum allocation (0–1)", "number", "1"],
              ["buy_threshold", "Buy threshold (return)", "number", "0.005"],
              ["sell_threshold", "Sell threshold (return)", "number", "-0.005"],
              ["folds", "Requested walk-forward folds", "number", "5"],
              ["holdout_fraction", "Holdout fraction", "number", "0.2"],
            ].map(([key, label, type, placeholder]) => (
              <div key={key}>
                <label className="label">{label}</label>
                <input
                  className="input-field"
                  type={type}
                  step="any"
                  value={options[key]}
                  placeholder={placeholder}
                  onChange={(event) => updateOption(key, event.target.value)}
                  disabled={loading}
                />
              </div>
            ))}
            <div>
              <label className="label">Signal source</label>
              <select
                className="input-field"
                value={options.signal_source}
                onChange={(event) => updateOption("signal_source", event.target.value)}
              >
                <option value="selected">Development-selected model</option>
                <option value="ensemble">Equal-weight ensemble</option>
              </select>
            </div>
            <div>
              <label className="label">Override model (optional)</label>
              <input
                className="input-field"
                value={options.model}
                placeholder="e.g. linear_regression"
                onChange={(event) => updateOption("model", event.target.value)}
              />
            </div>
          </div>
          {!isAdmin && (
            <p className="text-xs text-amber-700 mt-3">
              Running simulations requires an administrator account. Existing reports are read-only.
            </p>
          )}
        </div>
      </div>

      <JobNotice job={job} error={error} />

      {!report && !loading && !error && (
        <EmptyState
          title="No backtest report found"
          message="Run a backtest to compare buy-and-hold, cash, persistence, model-directional, and threshold strategies on the same out-of-sample forecast path."
        />
      )}

      {report && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <MetricCard
              label="Buy-and-hold total return"
              value={formatPct(buyHold?.equity_metrics?.total_return_pct, 2)}
              subtext={`${report.data?.evaluation_rows || 0} execution rows`}
              tone="slate"
            />
            <MetricCard
              label="Selected strategy return"
              value={formatPct(metrics.total_return_pct, 2)}
              subtext={`${STRATEGY_LABELS[selectedStrategy] || selectedStrategy} · Sharpe ${formatNumber(metrics.sharpe_ratio, 2)}`}
              tone="blue"
            />
            <MetricCard
              label="Highest simulated return"
              value={STRATEGY_LABELS[report.highest_simulated_return_strategy] || "—"}
              subtext="Descriptive only; not a profitability claim"
              tone="violet"
            />
            <MetricCard
              label="Model"
              value={modelLabel(report.model?.name)}
              subtext={`Signal source: ${report.model?.source || "—"}`}
              tone="amber"
            />
          </div>

          <Section
            title="Strategy comparison"
            subtitle="All strategies use the same prediction rows, execution timing, costs, and forced final liquidation. Select a row to inspect its equity curve and trades."
          >
            <SimpleTable
              columns={[
                { key: "strategy", label: "Strategy", render: (row) => (
                  <button
                    type="button"
                    className="font-medium text-blue-600 hover:underline"
                    onClick={() => setSelectedStrategy(row.strategy)}
                  >
                    {row.label || STRATEGY_LABELS[row.strategy] || row.strategy}
                  </button>
                ) },
                { key: "final", label: "Final equity", align: "right", render: (row) => formatNumber(row.final_equity, 2) },
                { key: "return", label: "Total return", align: "center", render: (row) => formatPct(row.total_return_pct, 2) },
                { key: "annual", label: "Annualized", align: "center", render: (row) => formatPct(row.annualized_return_pct, 2) },
                { key: "vol", label: "Volatility", align: "center", render: (row) => formatPct(row.annualized_volatility_pct, 2) },
                { key: "sharpe", label: "Sharpe", align: "center", render: (row) => formatNumber(row.sharpe_ratio, 2) },
                { key: "sortino", label: "Sortino", align: "center", render: (row) => formatNumber(row.sortino_ratio, 2) },
                { key: "drawdown", label: "Max drawdown", align: "center", render: (row) => formatPct(row.max_drawdown_pct, 2) },
                { key: "trades", label: "Trades", align: "center" },
                { key: "win", label: "Win rate", align: "center", render: (row) => formatPct(row.win_rate_pct, 1) },
                { key: "costs", label: "Costs", align: "right", render: (row) => formatNumber(row.transaction_costs, 2) },
              ]}
              rows={comparison.map((row) => ({ ...row, key: row.strategy }))}
            />
          </Section>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Section title="Equity curve" subtitle={`${STRATEGY_LABELS[selectedStrategy] || selectedStrategy} versus buy-and-hold. Simulated equity, not a live account.`}>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={equityChart} margin={{ top: 4, right: 8, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 9 }} minTickGap={24} />
                    <YAxis tick={{ fontSize: 9 }} />
                    <Tooltip formatter={(value) => formatNumber(value, 2)} />
                    <Legend />
                    <Line type="monotone" dataKey="selected" stroke="#2563eb" dot={false} name={STRATEGY_LABELS[selectedStrategy] || selectedStrategy} />
                    <Line type="monotone" dataKey="buyHold" stroke="#94a3b8" dot={false} name="Buy and hold" />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Section>

            <Section title="Drawdown" subtitle="Peak-to-trough decline of the selected strategy. Negative percentages are losses from a running peak.">
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={drawdownChart} margin={{ top: 4, right: 8, left: 0, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 9 }} minTickGap={24} />
                    <YAxis tick={{ fontSize: 9 }} />
                    <Tooltip formatter={(value) => formatPct(value, 2)} />
                    <Area type="monotone" dataKey="drawdown" stroke="#e11d48" fill="#fecdd3" name="Drawdown %" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Section>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Section title="Risk metrics" subtitle="Computed from the simulated equity curve. Sharpe and Sortino use the configured risk-free rate and 252 periods per year.">
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ["Final equity", formatNumber(metrics.final_equity, 2)],
                  ["Total return", formatPct(metrics.total_return_pct, 2)],
                  ["Annualized return", formatPct(metrics.annualized_return_pct, 2)],
                  ["Annualized volatility", formatPct(metrics.annualized_volatility_pct, 2)],
                  ["Sharpe ratio", formatNumber(metrics.sharpe_ratio, 3)],
                  ["Sortino ratio", formatNumber(metrics.sortino_ratio, 3)],
                  ["Maximum drawdown", formatPct(metrics.max_drawdown_pct, 2)],
                  ["Calmar ratio", formatNumber(metrics.calmar_ratio, 3)],
                  ["Best period", formatPct(metrics.best_period_return_pct, 2)],
                  ["Worst period", formatPct(metrics.worst_period_return_pct, 2)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className="font-semibold text-gray-800">{value}</p>
                  </div>
                ))}
              </div>
            </Section>

            <Section title="Trade statistics" subtitle="Closed trades only for win rate and profit factor. The final open position is liquidated at the final close for accounting.">
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  ["Total trades", strategy?.trade_metrics?.total_trades ?? "—"],
                  ["Closed trades", strategy?.trade_metrics?.closed_trades ?? "—"],
                  ["Win rate", formatPct(strategy?.trade_metrics?.win_rate_pct, 1)],
                  ["Profit factor", formatNumber(strategy?.trade_metrics?.profit_factor, 3)],
                  ["Average trade return", formatPct(strategy?.trade_metrics?.average_trade_return_pct, 2)],
                  ["Average holding days", formatNumber(strategy?.trade_metrics?.average_holding_days, 1)],
                  ["Net profit", formatNumber(strategy?.trade_metrics?.net_profit, 2)],
                  ["Transaction costs", formatNumber(strategy?.trade_metrics?.total_transaction_costs, 2)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs text-gray-500">{label}</p>
                    <p className="font-semibold text-gray-800">{value}</p>
                  </div>
                ))}
              </div>
            </Section>
          </div>

          <Section title="Trade history" subtitle="First 200 simulated trades for the selected strategy. Entry and exit costs are included in net P&L.">
            <SimpleTable
              columns={[
                { key: "entry", label: "Entry", render: (row) => row.entry_date },
                { key: "exit", label: "Exit", render: (row) => row.exit_date },
                { key: "entryPrice", label: "Entry price", align: "right", render: (row) => formatNumber(row.entry_price, 4) },
                { key: "exitPrice", label: "Exit price", align: "right", render: (row) => formatNumber(row.exit_price, 4) },
                { key: "net", label: "Net P&L", align: "right", render: (row) => formatNumber(row.net_pnl, 2) },
                { key: "return", label: "Return", align: "center", render: (row) => formatPct(row.net_return_pct, 2) },
                { key: "costs", label: "Costs", align: "right", render: (row) => formatNumber(row.total_costs, 2) },
                { key: "holding", label: "Holding sessions", align: "center", render: (row) => row.holding_days },
              ]}
              rows={tradeRows}
              empty="No trades were generated by this strategy."
            />
          </Section>

          <Section title="Execution scope" subtitle="Out-of-sample prediction rows only. The final holdout is part of this simulation but is not used to choose the model.">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 text-sm">
              <div><p className="text-xs text-gray-500">Generated</p><p className="font-medium">{formatDate(report.generated_at)}</p></div>
              <div><p className="text-xs text-gray-500">Period</p><p className="font-medium">{report.data?.first_execution_date} to {report.data?.last_execution_date}</p></div>
              <div><p className="text-xs text-gray-500">Fingerprint</p><p className="font-mono text-xs break-all">{report.data?.data_fingerprint_sha256}</p></div>
              <div><p className="text-xs text-gray-500">Status</p><StatusBadge status={report.status} /></div>
            </div>
          </Section>

          <WarningList warnings={report.warnings} />
          <Section title="Limitations" subtitle="A backtest is a historical simulation, not evidence of future profitability.">
            <ul className="list-disc pl-5 space-y-2 text-sm text-gray-600">
              {(report.limitations || []).map((limitation, index) => <li key={index}>{limitation}</li>)}
            </ul>
          </Section>
        </>
      )}
    </div>
  );
};

export default BacktestingPage;
