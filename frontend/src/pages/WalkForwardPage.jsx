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

const WalkForwardPage = () => {
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

  useEffect(() => {
    if (!symbol) return;
    loadLatest();
  }, [symbol]);

  const loadLatest = async () => {
    setError("");
    setJob(null);
    try {
      const data = await researchService.latestWalkForward(symbol);
      setReport(data);
    } catch (err) {
      if (err?.response?.status === 404) {
        setReport(null);
      } else {
        setError(errorMessage(err, "Failed to load the walk-forward report"));
      }
    }
  };

  const runExperiment = async () => {
    if (!symbol) return;
    setLoading(true);
    setError("");
    try {
      const response = await researchService.runWalkForward(symbol, {});
      const runningJob = response.job;
      setJob(runningJob);
      const completed = await researchService.waitForJob(
        runningJob.job_id,
        {
          onUpdate: setJob,
        }
      );
      setJob(completed);
      if (completed.result) {
        setReport(completed.result);
      } else {
        await loadLatest();
      }
      toast.success("Walk-forward evaluation completed");
    } catch (err) {
      setError(errorMessage(err, "Walk-forward evaluation failed"));
      toast.error("Walk-forward evaluation failed");
    } finally {
      setLoading(false);
    }
  };

  const selected = report?.best_performing_model?.selected_model;
  const development = report?.development_validation;
  const holdout = report?.final_holdout;
  const aggregated = development?.aggregated || {};
  const baselineName = report?.baseline_comparison?.baseline_name || "naive_persistence";
  const modelRows = Object.entries(aggregated)
    .filter(([, entry]) => entry?.metrics)
    .map(([name, entry]) => ({ key: name, name, ...entry.metrics, status: entry.status }));
  const foldRows = (development?.folds || []).map((fold) => ({
    key: fold.fold,
    fold: fold.fold,
    status: fold.status,
    train: fold.train,
    validation: fold.validation,
  }));
  const chartData = modelRows
    .filter((row) => row.rmse !== null)
    .map((row) => ({ name: modelLabel(row.name), rmse: row.rmse }));
  const selectedDevelopment =
    report?.best_performing_model?.development_metrics ||
    development?.model_selection?.selected_model_development_metrics;
  const selectedHoldout =
    report?.best_performing_model?.final_holdout_metrics ||
    holdout?.models?.[selected]?.metrics;

  return (
    <div className="space-y-6">
      <ResearchHeader
        title="Walk-forward evaluation"
        description="Chronological expanding-window evaluation with a locked final holdout, persistence baseline, and abstention-aware directional metrics. Zero movement is treated as an abstention."
        onRefresh={loadLatest}
        onRun={runExperiment}
        runLabel="Run walk-forward"
        loading={loading}
        canRun={isAdmin && Boolean(symbol)}
      />

      <div className="bg-white rounded-xl shadow-md p-5">
        <SymbolPicker value={symbol} onChange={setSymbol} disabled={loading} />
        {!isAdmin && (
          <p className="text-xs text-amber-700 mt-3">
            Running experiments requires an administrator account. Read-only reports are available to all signed-in users.
          </p>
        )}
      </div>

      <JobNotice job={job} error={error} />

      {!report && !loading && !error && (
        <EmptyState
          title="No walk-forward report found"
          message="An administrator can run the chronological evaluation for the selected stock. The report will appear here after the background job completes."
        />
      )}

      {report && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <MetricCard
              label="Selected model"
              value={modelLabel(selected)}
              subtext={`${report.sample_counts?.folds || 0} folds · ${report.sample_counts?.development_validation_samples || 0} development validation rows`}
              tone="violet"
            />
            <MetricCard
              label="Development RMSE"
              value={formatNumber(selectedDevelopment?.rmse, 4)}
              subtext={`Baseline ${formatNumber(aggregated[baselineName]?.metrics?.rmse, 4)}`}
              tone="blue"
            />
            <MetricCard
              label="Holdout RMSE"
              value={formatNumber(selectedHoldout?.rmse, 4)}
              subtext={`Baseline ${formatNumber(holdout?.models?.[baselineName]?.metrics?.rmse, 4)}`}
              tone="amber"
            />
            <MetricCard
              label="Holdout directional accuracy"
              value={formatPct(selectedHoldout?.directional_accuracy, 2)}
              subtext={`Coverage ${formatPct(selectedHoldout?.signal_coverage, 1)} · abstention ${formatPct(selectedHoldout?.abstention_rate, 1)}`}
              tone="green"
            />
          </div>

          <Section
            title="Experiment scope"
            subtitle="The final holdout is recorded after development-based model selection and is never used to tune a model or ensemble weight."
          >
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 text-sm">
              <div>
                <p className="text-xs text-gray-500">Generated</p>
                <p className="font-medium">{formatDate(report.generated_at)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Feature period</p>
                <p className="font-medium">
                  {report.data?.feature_period?.start} to {report.data?.feature_period?.end}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Data fingerprint</p>
                <p className="font-mono text-xs break-all">{report.data?.data_fingerprint_sha256}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Status</p>
                <StatusBadge status={report.status} />
              </div>
            </div>
          </Section>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <Section title="Development model comparison" subtitle="Pooled chronological validation. Lower error is better; directional metrics exclude abstentions.">
              <div className="h-56 mb-4">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 30 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={60} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(value) => formatNumber(value, 4)} />
                    <Bar dataKey="rmse" fill="#3b82f6" name="RMSE" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <SimpleTable
                columns={[
                  { key: "name", label: "Candidate", render: (row) => modelLabel(row.name) },
                  { key: "rmse", label: "RMSE", align: "center", render: (row) => formatNumber(row.rmse) },
                  { key: "mae", label: "MAE", align: "center", render: (row) => formatNumber(row.mae) },
                  { key: "nmae_pct", label: "nMAE", align: "center", render: (row) => formatPct(row.nmae_pct, 2) },
                  { key: "mase", label: "MASE", align: "center", render: (row) => formatNumber(row.mase_vs_random_walk, 3) },
                  { key: "coverage", label: "Coverage", align: "center", render: (row) => formatPct(row.signal_coverage, 1) },
                  { key: "direction", label: "Direction", align: "center", render: (row) => formatPct(row.directional_accuracy, 1) },
                ]}
                rows={modelRows}
              />
            </Section>

            <Section title="Final holdout" subtitle="Reported after selection was locked. This is a single chronological period, not a guarantee of future performance.">
              <SimpleTable
                columns={[
                  { key: "name", label: "Candidate", render: (row) => modelLabel(row.name) },
                  { key: "rmse", label: "RMSE", align: "center", render: (row) => formatNumber(row.rmse) },
                  { key: "mae", label: "MAE", align: "center", render: (row) => formatNumber(row.mae) },
                  { key: "r2", label: "R²", align: "center", render: (row) => formatNumber(row.r2_score, 3) },
                  { key: "coverage", label: "Coverage", align: "center", render: (row) => formatPct(row.signal_coverage, 1) },
                  { key: "direction", label: "Direction", align: "center", render: (row) => formatPct(row.directional_accuracy, 1) },
                ]}
                rows={Object.entries(holdout?.models || {})
                  .filter(([, entry]) => entry?.metrics)
                  .map(([name, entry]) => ({ key: name, name, ...entry.metrics }))}
              />
              <div className="mt-4 rounded-lg bg-slate-50 p-4 text-xs text-slate-600">
                The baseline predicts the current close and therefore abstains from directional movement. Its directional accuracy is reported as null, not as a fabricated 0%.
              </div>
            </Section>
          </div>

          <Section title="Fold boundaries" subtitle="Contiguous chronological blocks; no shuffling and no overlapping validation targets.">
            <SimpleTable
              columns={[
                { key: "fold", label: "Fold", align: "center" },
                { key: "status", label: "Status", align: "center", render: (row) => <StatusBadge status={row.status} /> },
                { key: "train", label: "Train rows", align: "center", render: (row) => row.train?.samples },
                { key: "trainPeriod", label: "Train period", render: (row) => `${row.train?.start} to ${row.train?.end}` },
                { key: "validation", label: "Validation rows", align: "center", render: (row) => row.validation?.samples },
                { key: "validationPeriod", label: "Validation target period", render: (row) => `${row.validation?.target_start} to ${row.validation?.target_end}` },
              ]}
              rows={foldRows}
            />
          </Section>

          <WarningList warnings={report.warnings} />
          <Section title="Limitations" subtitle="Read these before interpreting the metrics.">
            <ul className="list-disc pl-5 space-y-2 text-sm text-gray-600">
              {(report.limitations || []).map((limitation, index) => (
                <li key={index}>{limitation}</li>
              ))}
            </ul>
          </Section>
        </>
      )}
    </div>
  );
};

export default WalkForwardPage;
