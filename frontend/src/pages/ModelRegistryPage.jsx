import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
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

const ModelRegistryPage = () => {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [searchParams] = useSearchParams();
  const [symbol, setSymbol] = useState(
    searchParams.get("symbol") || "TATASTEEL.NS"
  );
  const [summary, setSummary] = useState(null);
  const [symbolState, setSymbolState] = useState(null);
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState("");

  useEffect(() => {
    loadSummary();
  }, []);

  useEffect(() => {
    if (symbol) loadSymbol();
  }, [symbol]);

  const loadSummary = async () => {
    try {
      setSummary(await researchService.listModels());
    } catch (err) {
      setError(errorMessage(err, "Failed to load the registry summary"));
    }
  };

  const loadSymbol = async () => {
    setError("");
    try {
      setSymbolState(await researchService.getSymbolModels(symbol));
    } catch (err) {
      setSymbolState(null);
      setError(errorMessage(err, "Failed to load the model registry"));
    }
  };

  const refresh = async () => {
    await Promise.all([loadSummary(), loadSymbol()]);
  };

  const trainCandidate = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await researchService.trainCandidate(symbol, {
        period: period || undefined,
      });
      setJob(response.job);
      const completed = await researchService.waitForJob(response.job.job_id, {
        onUpdate: setJob,
      });
      setJob(completed);
      await refresh();
      toast.success("Candidate trained and registered");
    } catch (err) {
      setError(errorMessage(err, "Candidate training failed"));
      toast.error("Candidate training failed");
    } finally {
      setLoading(false);
    }
  };

  const approve = async (version, approved = true) => {
    try {
      await researchService.approveCandidate(symbol, version, approved);
      await refresh();
      toast.success(approved ? "Candidate approved" : "Approval removed");
    } catch (err) {
      setError(errorMessage(err, "Approval update failed"));
    }
  };

  const activate = async (version) => {
    if (!window.confirm(`Activate ${version} for ${symbol}? This changes the active registered model used by the v2 prediction endpoint, not the legacy saved_models path.`)) return;
    try {
      await researchService.activateCandidate(symbol, version, true);
      await refresh();
      toast.success(`${version} activated`);
    } catch (err) {
      setError(errorMessage(err, "Activation failed"));
    }
  };

  const rollback = async () => {
    if (!window.confirm(`Roll back ${symbol} to its previously active registered version?`)) return;
    try {
      await researchService.rollbackModel(symbol, true);
      await refresh();
      toast.success("Rollback completed");
    } catch (err) {
      setError(errorMessage(err, "Rollback failed"));
    }
  };

  const deactivate = async () => {
    if (!window.confirm(`Deactivate the registered model for ${symbol}? The v2 prediction endpoint will have no active model until another version is activated.`)) return;
    try {
      await researchService.deactivateModel(symbol);
      await refresh();
      toast.success("Registered model deactivated");
    } catch (err) {
      setError(errorMessage(err, "Deactivation failed"));
    }
  };

  const registry = symbolState?.registry || {};
  const versions = symbolState?.versions || [];
  const activeVersion = registry.active_version;
  const activeEntry = versions.find((version) => version.version === activeVersion);
  const rows = [...versions].reverse().map((entry) => {
    const ensembleMetrics = entry.validation?.models?.ensemble_equal_weight;
    return {
      key: entry.version,
      ...entry,
      ensembleMetrics,
      isActive: entry.version === activeVersion,
    };
  });

  return (
    <div className="space-y-6">
      <ResearchHeader
        title="Model registry & lifecycle"
        description="Versioned research candidates, explicit approval, controlled activation, rollback, and artifact validation. Registry artifacts live separately from the legacy saved_models path and are never overwritten by retraining."
        onRefresh={refresh}
        onRun={trainCandidate}
        runLabel="Train candidate"
        loading={loading}
        canRun={isAdmin && Boolean(symbol)}
      />

      <div className="bg-white rounded-xl shadow-md p-5 space-y-4">
        <SymbolPicker value={symbol} onChange={setSymbol} disabled={loading} />
        <div className="flex flex-col sm:flex-row sm:items-end gap-3">
          <div className="w-full sm:w-64">
            <label className="label">Training period (optional)</label>
            <input className="input-field" value={period} onChange={(event) => setPeriod(event.target.value)} placeholder="use service default" />
          </div>
          {activeVersion && (
            <div className="flex gap-2">
              <button type="button" className="btn-secondary" onClick={rollback} disabled={!isAdmin}>
                Roll back
              </button>
              <button type="button" className="btn-secondary" onClick={deactivate} disabled={!isAdmin}>
                Deactivate
              </button>
            </div>
          )}
        </div>
        {!isAdmin && (
          <p className="text-xs text-amber-700">
            Training, approval, activation, rollback, and deactivation require an administrator account.
          </p>
        )}
      </div>

      <JobNotice job={job} error={error} />

      {summary && (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <MetricCard label="Registered symbols" value={summary.total_symbols} tone="blue" />
          <MetricCard label="Total versions" value={summary.total_versions} tone="violet" />
          <MetricCard label="Active version" value={activeVersion || "None"} subtext={symbol} tone="green" />
          <MetricCard label="Candidate versions" value={rows.filter((row) => row.status === "candidate").length} subtext="Awaiting approval or activation" tone="amber" />
        </div>
      )}

      {!activeEntry && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          No registered model is active for {symbol}. The legacy prediction path remains unchanged; the v2 registered-model prediction endpoint will return a conflict until a candidate is approved and activated.
        </div>
      )}

      {activeEntry && (
        <Section title={`Active version · ${activeEntry.version}`} subtitle="Only this explicitly activated version is used by the v2 registered-model prediction endpoint.">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 text-sm">
            <div><p className="text-xs text-gray-500">Model ID</p><p className="font-mono text-xs break-all">{activeEntry.model_id}</p></div>
            <div><p className="text-xs text-gray-500">Activated</p><p className="font-medium">{formatDate(activeEntry.activated_at)}</p></div>
            <div><p className="text-xs text-gray-500">Approved by</p><p className="font-medium">{activeEntry.approved_by || "—"}</p></div>
            <div><p className="text-xs text-gray-500">Validation RMSE</p><p className="font-medium">{formatNumber(activeEntry.validation?.models?.ensemble_equal_weight?.rmse, 4)}</p></div>
          </div>
          <div className="mt-4 rounded-lg bg-slate-50 p-4 text-xs text-slate-600">
            Artifact schema: {activeEntry.artifact_compatibility?.schema_version} · Target: {activeEntry.target_formulation} · Feature columns: {activeEntry.feature_columns?.length}
          </div>
        </Section>
      )}

      {!versions.length && !loading && (
        <EmptyState title="No versions registered" message="Train a candidate to create an immutable versioned artifact set under the research registry. Training does not activate the model or overwrite saved_models." />
      )}

      {versions.length > 0 && (
        <Section title="Version history" subtitle="Candidates must be explicitly approved before activation. Retraining always creates a new version rather than overwriting an existing artifact.">
          <SimpleTable
            columns={[
              { key: "version", label: "Version", render: (row) => <span className="font-semibold">{row.version}</span> },
              { key: "status", label: "Status", align: "center", render: (row) => (
                <div className="flex flex-col items-center gap-1">
                  <StatusBadge status={row.status} />
                  {row.isActive && <span className="text-[10px] text-emerald-600">active</span>}
                </div>
              ) },
              { key: "approved", label: "Approved", align: "center", render: (row) => row.approved ? "Yes" : "No" },
              { key: "created", label: "Created", render: (row) => formatDate(row.created_at) },
              { key: "validation", label: "Ensemble RMSE", align: "center", render: (row) => formatNumber(row.ensembleMetrics?.rmse, 4) },
              { key: "coverage", label: "Coverage", align: "center", render: (row) => formatPct(row.ensembleMetrics?.signal_coverage, 1) },
              { key: "direction", label: "Direction", align: "center", render: (row) => formatPct(row.ensembleMetrics?.directional_accuracy, 1) },
              { key: "vsActive", label: "RMSE vs active", align: "center", render: (row) => row.candidate_vs_active ? formatPct(row.candidate_vs_active.rmse_improvement_pct, 2) : "—" },
              { key: "actions", label: "Actions", align: "right", render: (row) => (
                <div className="flex flex-wrap justify-end gap-2">
                  {!row.approved && <button type="button" className="text-xs text-blue-600 hover:underline" disabled={!isAdmin} onClick={() => approve(row.version, true)}>Approve</button>}
                  {row.approved && <button type="button" className="text-xs text-slate-500 hover:underline" disabled={!isAdmin} onClick={() => approve(row.version, false)}>Unapprove</button>}
                  {!row.isActive && <button type="button" className="text-xs text-emerald-600 hover:underline" disabled={!isAdmin || !row.approved} onClick={() => activate(row.version)}>Activate</button>}
                </div>
              ) },
            ]}
            rows={rows}
          />
        </Section>
      )}

      {activeEntry && (
        <Section title="Active candidate validation" subtitle="Chronological test metrics stored when the candidate was created. These are not a guarantee of future performance.">
          <SimpleTable
            columns={[
              { key: "name", label: "Candidate", render: (row) => modelLabel(row.name) },
              { key: "rmse", label: "RMSE", align: "center", render: (row) => formatNumber(row.rmse, 4) },
              { key: "mae", label: "MAE", align: "center", render: (row) => formatNumber(row.mae, 4) },
              { key: "nmae", label: "nMAE", align: "center", render: (row) => formatPct(row.nmae_pct, 2) },
              { key: "coverage", label: "Coverage", align: "center", render: (row) => formatPct(row.signal_coverage, 1) },
              { key: "direction", label: "Direction", align: "center", render: (row) => formatPct(row.directional_accuracy, 1) },
            ]}
            rows={Object.entries(activeEntry.validation?.models || {})
              .filter(([, entry]) => entry)
              .map(([name, metrics]) => ({ key: name, name, ...metrics }))}
          />
          <WarningList warnings={[
            "Registry candidates use a chronological train/test split, not the Phase 2 walk-forward holdout. Compare versions with caution.",
            "No registry version is written to saved_models, and activation changes only the v2 registered-model prediction path.",
          ]} />
        </Section>
      )}
    </div>
  );
};

export default ModelRegistryPage;
