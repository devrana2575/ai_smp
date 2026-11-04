import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
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

const FAMILY_LABELS = {
  absolute_price: "Absolute price",
  simple_return: "Simple return",
  log_return: "Log return",
};

const FAMILY_DESCRIPTIONS = {
  absolute_price: "Target is Next_Day_Close; reconstruction is the forecast itself.",
  simple_return: "Target is Close[t+1]/Close[t] - 1; reconstruct as current close × (1 + forecast).",
  log_return: "Target is log(Close[t+1]/Close[t]); reconstruct as current close × exp(forecast).",
};

const ReturnForecastingPage = () => {
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
  const [family, setFamily] = useState("absolute_price");

  useEffect(() => {
    if (!symbol) return;
    loadLatest();
  }, [symbol]);

  const loadLatest = async () => {
    setError("");
    setJob(null);
    try {
      const data = await researchService.latestReturnExperiment(symbol);
      setReport(data);
    } catch (err) {
      if (err?.response?.status === 404) {
        setReport(null);
      } else {
        setError(errorMessage(err, "Failed to load the return experiment"));
      }
    }
  };

  const runExperiment = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await researchService.runReturnExperiment(symbol, {});
      setJob(response.job);
      const completed = await researchService.waitForJob(response.job.job_id, {
        onUpdate: setJob,
      });
      setJob(completed);
      if (completed.result) setReport(completed.result);
      else await loadLatest();
      toast.success("Return-target experiment completed");
    } catch (err) {
      setError(errorMessage(err, "Return-target experiment failed"));
      toast.error("Return-target experiment failed");
    } finally {
      setLoading(false);
    }
  };

  const comparison = report?.final_holdout_comparison;
  const rows = comparison?.rows || [];
  const chartData = rows
    .filter((row) => row.best_model_price_metrics?.rmse !== null)
    .map((row) => ({
      family: FAMILY_LABELS[row.family] || row.family,
      rmse: row.best_model_price_metrics?.rmse,
    }));
  const selectedFamily = report?.families?.[family];
  const familyModels = Object.entries(selectedFamily?.final_holdout?.models || {})
    .filter(([, entry]) => entry?.price_metrics)
    .map(([name, entry]) => ({
      key: name,
      name,
      ...entry.price_metrics,
      returnDirection: entry.return_metrics?.directional_accuracy,
      returnCoverage: entry.return_metrics?.signal_coverage,
    }));

  return (
    <div className="space-y-6">
      <ResearchHeader
        title="Return-target experiment"
        description="Compare absolute-price forecasts with simple-return and log-return targets under the identical Phase 2 chronological folds and locked holdout. Reconstructed prices and return metrics are reported separately; the zero-return baseline abstains."
        onRefresh={loadLatest}
        onRun={runExperiment}
        runLabel="Run return experiment"
        loading={loading}
        canRun={isAdmin && Boolean(symbol)}
      />

      <div className="bg-white rounded-xl shadow-md p-5">
        <SymbolPicker value={symbol} onChange={setSymbol} disabled={loading} />
        {!isAdmin && (
          <p className="text-xs text-amber-700 mt-3">
            Running experiments requires an administrator account. Reports are read-only for other signed-in users.
          </p>
        )}
      </div>

      <JobNotice job={job} error={error} />

      {!report && !loading && !error && (
        <EmptyState
          title="No return experiment found"
          message="Run the experiment to compare absolute-price, simple-return, and log-return targets on the same chronological folds and holdout."
        />
      )}

      {report && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <MetricCard
              label="Best price family (holdout)"
              value={FAMILY_LABELS[comparison?.best_family_by_price_rmse] || "—"}
              subtext={`Absolute price family: ${report.sample_counts?.folds || 0} folds`}
              tone="violet"
            />
            <MetricCard
              label="Best return family (holdout)"
              value={FAMILY_LABELS[comparison?.best_family_by_return_rmse] || "—"}
              subtext={`Holdout rows: ${report.sample_counts?.holdout_validation_samples || 0}`}
              tone="blue"
            />
            <MetricCard
              label="Zero-return baseline RMSE"
              value={formatNumber(comparison?.absolute_family_zero_return_price_rmse, 4)}
              subtext="Absolute price reconstruction"
              tone="slate"
            />
            <MetricCard
              label="Production inference"
              value={report.production_inference_changed ? "Changed" : "Unchanged"}
              subtext={'The experiment does not alter saved models or the legacy prediction path.'}
              tone="green"
            />
          </div>

          <Section
            title="Holdout comparison"
            subtitle="Each family's best development candidate is reported on the final holdout. The holdout was not used to tune or select these models."
          >
            <div className="h-56 mb-5">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="family" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip formatter={(value) => formatNumber(value, 4)} />
                  <Bar dataKey="rmse" fill="#8b5cf6" name="Reconstructed price RMSE" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <SimpleTable
              columns={[
                { key: "family", label: "Target family", render: (row) => FAMILY_LABELS[row.family] || row.family },
                { key: "best", label: "Best candidate", render: (row) => modelLabel(row.best_model_by_price_rmse) },
                { key: "rmse", label: "Price RMSE", align: "center", render: (row) => formatNumber(row.best_model_price_metrics?.rmse, 4) },
                { key: "nmape", label: "nMAE", align: "center", render: (row) => formatPct(row.best_model_price_metrics?.nmae_pct, 2) },
                { key: "returnRmse", label: "Return RMSE", align: "center", render: (row) => formatNumber(row.best_model_return_metrics?.rmse, 8) },
                { key: "coverage", label: "Coverage", align: "center", render: (row) => formatPct(row.best_model_return_metrics?.signal_coverage, 1) },
                { key: "direction", label: "Direction", align: "center", render: (row) => formatPct(row.best_model_return_metrics?.directional_accuracy, 1) },
                { key: "baseline", label: "Zero-return RMSE", align: "center", render: (row) => formatNumber(row.zero_return_price_metrics?.rmse, 4) },
              ]}
              rows={rows}
            />
            <div className="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
              <p className="font-semibold">Recommendation</p>
              <p className="mt-1 text-xs leading-5">{comparison?.recommendation}</p>
            </div>
          </Section>

          <Section
            title="Family detail"
            subtitle="Inspect the final-holdout candidates for one target formulation. Directional accuracy is null for the zero-return baseline because it abstains."
            actions={
              <select className="input-field max-w-xs" value={family} onChange={(event) => setFamily(event.target.value)}>
                {Object.keys(report.families || {}).map((key) => (
                  <option key={key} value={key}>{FAMILY_LABELS[key] || key}</option>
                ))}
              </select>
            }
          >
            <p className="text-xs text-gray-500 mb-3">{FAMILY_DESCRIPTIONS[family]}</p>
            <SimpleTable
              columns={[
                { key: "name", label: "Candidate", render: (row) => modelLabel(row.name) },
                { key: "rmse", label: "Price RMSE", align: "center", render: (row) => formatNumber(row.rmse, 4) },
                { key: "mae", label: "Price MAE", align: "center", render: (row) => formatNumber(row.mae, 4) },
                { key: "nrmse", label: "nRMSE", align: "center", render: (row) => formatPct(row.nrmse_pct, 2) },
                { key: "mase", label: "MASE", align: "center", render: (row) => formatNumber(row.mase_vs_random_walk, 3) },
                { key: "coverage", label: "Return coverage", align: "center", render: (row) => formatPct(row.returnCoverage, 1) },
                { key: "direction", label: "Direction", align: "center", render: (row) => formatPct(row.returnDirection, 1) },
              ]}
              rows={familyModels}
            />
          </Section>

          <Section title="Experiment scope" subtitle="The same EvaluationConfig, feature dataset, fold generator, and holdout split were used for every family.">
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 text-sm">
              <div><p className="text-xs text-gray-500">Generated</p><p className="font-medium">{formatDate(report.generated_at)}</p></div>
              <div><p className="text-xs text-gray-500">Feature period</p><p className="font-medium">{report.data?.feature_period?.start} to {report.data?.feature_period?.end}</p></div>
              <div><p className="text-xs text-gray-500">Folds</p><p className="font-medium">{report.sample_counts?.folds}</p></div>
              <div><p className="text-xs text-gray-500">Status</p><StatusBadge status={report.status} /></div>
            </div>
          </Section>

          <WarningList warnings={report.warnings} />
          <Section title="Limitations" subtitle="Return forecasts can be numerically valid but economically unreliable.">
            <ul className="list-disc pl-5 space-y-2 text-sm text-gray-600">
              {(report.limitations || []).map((limitation, index) => <li key={index}>{limitation}</li>)}
            </ul>
          </Section>
        </>
      )}
    </div>
  );
};

export default ReturnForecastingPage;
