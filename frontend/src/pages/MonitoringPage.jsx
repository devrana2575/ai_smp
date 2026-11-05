import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import { useAuth } from "../context/AuthContext";
import { researchService, errorMessage } from "../services/researchService";
import {
  EmptyState,
  MetricCard,
  ResearchHeader,
  Section,
  SimpleTable,
  StatusBadge,
  SymbolPicker,
  WarningList,
  formatNumber,
  formatPct,
} from "../components/research/ResearchUi";

const MonitoringPage = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [searchParams] = useSearchParams();
  const [symbol, setSymbol] = useState(
    searchParams.get("symbol") || "TATASTEEL.NS"
  );
  const [summary, setSummary] = useState(null);
  const [drift, setDrift] = useState(null);
  const [predictions, setPredictions] = useState(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [prediction, setPrediction] = useState(null);

  useEffect(() => {
    if (symbol) loadAll(1);
  }, [symbol]);

  const loadAll = async (nextPage = page) => {
    setError("");
    setLoading(true);
    try {
      const [summaryData, driftData, predictionData] = await Promise.all([
        researchService.monitoringSummary(symbol),
        researchService.monitoringDrift(symbol),
        researchService.monitoringPredictions(symbol, nextPage, 20),
      ]);
      setSummary(summaryData);
      setDrift(driftData);
      setPredictions(predictionData);
      setPage(nextPage);
    } catch (err) {
      setError(errorMessage(err, "Failed to load monitoring data"));
    } finally {
      setLoading(false);
    }
  };

  const updateActuals = async () => {
    setLoading(true);
    try {
      const result = await researchService.updateActuals(symbol);
      toast.success(`Updated ${result.updated} prediction outcome(s)`);
      await loadAll(page);
    } catch (err) {
      setError(errorMessage(err, "Failed to update actual outcomes"));
      toast.error("Failed to update actual outcomes");
    } finally {
      setLoading(false);
    }
  };

  const runPrediction = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await researchService.predictRegistered(symbol);
      setPrediction(result);
      toast.success("Registered-model prediction recorded");
      await loadAll(1);
    } catch (err) {
      setError(errorMessage(err, "Registered-model prediction failed"));
      toast.error("Registered-model prediction failed");
    } finally {
      setLoading(false);
    }
  };

  const metrics = summary?.tracking_metrics?.metrics;
  const driftRows = drift?.drift?.features || [];
  const predictionRows = predictions?.items || [];
  const freshness = summary?.data_freshness;
  const pageCount = predictions?.total_pages || 1;

  return (
    <div className="space-y-6">
      <ResearchHeader
        title="Prediction monitoring & drift"
        description="Track registered-model predictions, attach realized next-session outcomes, and inspect feature drift. Monitoring metrics only include completed predictions; pending forecasts are never counted as correct or incorrect."
        onRefresh={() => loadAll(page)}
        onRun={runPrediction}
        runLabel="Predict with active model"
        loading={loading}
        canRun={Boolean(symbol)}
        extra={
          <button type="button" className="btn-secondary" onClick={updateActuals} disabled={loading || !isAdmin} title={!isAdmin ? "Administrator access is required" : undefined}>
            Update actual outcomes
          </button>
        }
      />

      <div className="bg-white rounded-xl shadow-md p-5">
        <SymbolPicker value={symbol} onChange={setSymbol} disabled={loading} />
        <p className="text-xs text-gray-500 mt-3">
          Prediction recording requires an active registered model. Updating actual outcomes fetches recent daily closes; a forecast remains pending until its next session is available.
        </p>
        {!isAdmin && <p className="text-xs text-amber-700 mt-2">Updating actual outcomes requires an administrator account.</p>}
      </div>

      {error && <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}

      {!summary && !loading && !error && (
        <EmptyState title="No monitoring data" message="No registered-model predictions have been recorded for this symbol yet." />
      )}

      {summary && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <MetricCard label="Tracked predictions" value={summary.record_counts?.total ?? 0} subtext={`${summary.record_counts?.completed ?? 0} completed · ${summary.record_counts?.pending ?? 0} pending`} tone="blue" />
            <MetricCard label="MAE" value={formatNumber(metrics?.mae, 4)} subtext="Completed predictions only" tone="violet" />
            <MetricCard label="Directional accuracy" value={formatPct(metrics?.directional_accuracy, 1)} subtext={`Coverage ${formatPct(metrics?.signal_coverage, 1)} · abstention ${formatPct(metrics?.abstention_rate, 1)}`} tone="green" />
            <MetricCard label="Data freshness" value={freshness?.latest_date || "Unavailable"} subtext={freshness?.status === "ok" ? `${freshness.rows} cleaned rows` : freshness?.error} tone={freshness?.status === "ok" ? "slate" : "red"} />
          </div>

          {prediction && (
            <Section title="Latest registered-model prediction" subtitle="Recorded in the monitoring store and, when using the backend proxy, saved to prediction history.">
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 text-sm">
                <div><p className="text-xs text-gray-500">Model</p><p className="font-medium">{prediction.model_id} · {prediction.model_version}</p></div>
                <div><p className="text-xs text-gray-500">Feature timestamp</p><p className="font-medium">{prediction.feature_timestamp}</p></div>
                <div><p className="text-xs text-gray-500">Current → predicted</p><p className="font-medium">{formatNumber(prediction.current_price, 2)} → {formatNumber(prediction.predicted_price, 2)}</p></div>
                <div><p className="text-xs text-gray-500">Signal</p><p className="font-medium">{prediction.signal} ({formatPct((prediction.predicted_return || 0) * 100, 2)})</p></div>
              </div>
            </Section>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Section title="Tracking metrics" subtitle="Only predictions with a matched actual next-session close are included. Pending forecasts are excluded rather than scored as zero.">
              {summary.tracking_metrics?.metrics ? (
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {[
                    ["Completed", summary.tracking_metrics.completed_predictions],
                    ["MAE", formatNumber(metrics.mae, 4)],
                    ["RMSE", formatNumber(metrics.rmse, 4)],
                    ["sMAPE", formatPct(metrics.smape, 2)],
                    ["Directional accuracy", formatPct(metrics.directional_accuracy, 2)],
                    ["Signal coverage", formatPct(metrics.signal_coverage, 1)],
                    ["Abstention rate", formatPct(metrics.abstention_rate, 1)],
                    ["Mean error", formatNumber(summary.tracking_metrics.mean_error, 4)],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg bg-slate-50 p-3">
                      <p className="text-xs text-gray-500">{label}</p>
                      <p className="font-semibold text-gray-800">{value}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-500">No completed predictions yet. Run a registered-model forecast, then update actual outcomes after the next session is available.</p>
              )}
              <WarningList warnings={summary.warnings} />
            </Section>

            <Section title="Feature drift" subtitle={drift?.drift?.method || "PSI over reference quantile bins, plus standardized mean shift. Warning-only."}>
              {drift?.drift?.status === "ok" ? (
                <>
                  <div className="flex flex-wrap items-center gap-4 text-sm mb-4">
                    <span>Max PSI: <strong>{formatNumber(drift.drift.max_psi, 3)}</strong></span>
                    <span>Threshold: <strong>{formatNumber(drift.drift.threshold, 3)}</strong></span>
                    <StatusBadge status={drift.drift.drift_detected ? "warning" : "ok"} />
                  </div>
                  <SimpleTable
                    columns={[
                      { key: "feature", label: "Feature" },
                      { key: "psi", label: "PSI", align: "center", render: (row) => formatNumber(row.psi, 4) },
                      { key: "shift", label: "Std. mean shift", align: "center", render: (row) => formatNumber(row.standardized_mean_shift, 3) },
                      { key: "flag", label: "Flag", align: "center", render: (row) => row.drift_detected ? <StatusBadge status="warning" /> : "—" },
                    ]}
                    rows={driftRows.map((row) => ({ ...row, key: row.feature }))}
                  />
                </>
              ) : (
                <p className="text-sm text-rose-600">{drift?.drift?.error || "Drift could not be computed."}</p>
              )}
            </Section>
          </div>

          <Section title="Prediction history" subtitle="Newest first. Directional correctness is computed only where both predicted and actual movement are non-zero.">
            <SimpleTable
              columns={[
                { key: "feature", label: "Feature date", render: (row) => row.feature_timestamp },
                { key: "model", label: "Model", render: (row) => <span title={row.model_id}>{row.model_version || "—"}</span> },
                { key: "signal", label: "Signal", align: "center", render: (row) => <StatusBadge status={row.signal || "unknown"} /> },
                { key: "current", label: "Current", align: "right", render: (row) => formatNumber(row.current_price, 2) },
                { key: "predicted", label: "Predicted", align: "right", render: (row) => formatNumber(row.predicted_price, 2) },
                { key: "actual", label: "Actual", align: "right", render: (row) => row.actual_price === null ? "Pending" : formatNumber(row.actual_price, 2) },
                { key: "error", label: "Error", align: "right", render: (row) => row.prediction_error === null || row.prediction_error === undefined ? "—" : formatNumber(row.prediction_error, 4) },
                { key: "direction", label: "Direction", align: "center", render: (row) => row.direction_correct === null ? "—" : row.direction_correct ? "Correct" : "Incorrect" },
                { key: "status", label: "Status", align: "center", render: (row) => <StatusBadge status={row.status} /> },
              ]}
              rows={predictionRows.map((row) => ({ ...row, key: row.prediction_id }))}
              empty="No predictions recorded for this symbol."
            />
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-gray-500">Page {page} of {pageCount} · {predictions?.total || 0} predictions</span>
              <div className="flex gap-2">
                <button type="button" className="btn-secondary" disabled={loading || page <= 1} onClick={() => loadAll(page - 1)}>Previous</button>
                <button type="button" className="btn-secondary" disabled={loading || page >= pageCount} onClick={() => loadAll(page + 1)}>Next</button>
              </div>
            </div>
          </Section>
        </>
      )}
    </div>
  );
};

export default MonitoringPage;
