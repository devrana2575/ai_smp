import { useEffect, useState } from "react";
import { companyService } from "../../services/companyService";

const DEFAULT_SYMBOLS = [
  "COALINDIA.NS",
  "HINDALCO.NS",
  "HINDZINC.NS",
  "JINDALSTEL.NS",
  "JSWSTEEL.NS",
  "TATASTEEL.NS",
];

export const MODEL_LABELS = {
  linear_regression: "Linear Regression",
  decision_tree: "Decision Tree",
  random_forest: "Random Forest",
  svr: "SVR",
  xgboost: "XGBoost",
  ensemble_equal_weight: "Equal-Weight Ensemble",
  naive_persistence: "Naive Persistence",
  zero_return_persistence: "Zero-Return Persistence",
};

export const modelLabel = (name) =>
  MODEL_LABELS[name] || (name ? name.replaceAll("_", " ") : "—");

export const formatNumber = (value, digits = 4) => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: Math.min(digits, 2),
  });
};

export const formatPct = (value, digits = 2) =>
  value === null || value === undefined ? "—" : `${formatNumber(value, digits)}%`;

export const formatDate = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString();
};

export const MetricCard = ({ label, value, subtext, tone = "blue" }) => {
  const tones = {
    blue: "from-blue-500 to-blue-600",
    green: "from-emerald-500 to-emerald-600",
    amber: "from-amber-500 to-amber-600",
    red: "from-rose-500 to-rose-600",
    slate: "from-slate-600 to-slate-700",
    violet: "from-violet-500 to-violet-600",
  };
  return (
    <div className={`rounded-xl p-5 text-white bg-gradient-to-br ${tones[tone] || tones.blue}`}>
      <p className="text-xs uppercase tracking-wide opacity-80">{label}</p>
      <p className="text-2xl font-bold mt-1 break-words">{value}</p>
      {subtext && <p className="text-xs opacity-75 mt-1">{subtext}</p>}
    </div>
  );
};

export const StatusBadge = ({ status }) => {
  const styles =
    status === "active" || status === "ok" || status === "completed"
      ? "bg-emerald-100 text-emerald-700"
      : status === "candidate" || status === "partial" || status === "queued"
      ? "bg-amber-100 text-amber-700"
      : status === "failed" || status === "inactive"
      ? "bg-rose-100 text-rose-700"
      : "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${styles}`}>
      {status || "unknown"}
    </span>
  );
};

export const ResearchHeader = ({
  title,
  description,
  onRefresh,
  onRun,
  loading,
  canRun = true,
  runLabel = "Run experiment",
  extra,
}) => (
  <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
    <div>
      <h2 className="text-2xl font-bold text-gray-800">{title}</h2>
      <p className="text-sm text-gray-500 max-w-3xl">{description}</p>
    </div>
    <div className="flex flex-wrap gap-2">
      {extra}
      {onRefresh && (
        <button type="button" onClick={onRefresh} className="btn-secondary">
          Refresh
        </button>
      )}
      {onRun && (
        <button
          type="button"
          onClick={onRun}
          disabled={loading || !canRun}
          className="btn-primary disabled:opacity-50"
          title={!canRun ? "Administrator access is required" : undefined}
        >
          {loading ? "Running..." : runLabel}
        </button>
      )}
    </div>
  </div>
);

export const SymbolPicker = ({ value, onChange, disabled = false }) => {
  const [companies, setCompanies] = useState([]);
  const [manual, setManual] = useState("");

  useEffect(() => {
    let mounted = true;
    companyService
      .getAll()
      .then((data) => {
        if (mounted && Array.isArray(data) && data.length) {
          setCompanies(data);
        }
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  const options = companies.length
    ? companies.map((company) => ({
        symbol: company.symbol,
        label: `${company.name} (${company.symbol})`,
      }))
    : DEFAULT_SYMBOLS.map((symbol) => ({ symbol, label: symbol }));

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
      <div className="min-w-[260px]">
        <label className="label">Stock</label>
        <select
          className="input-field"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
        >
          <option value="">Select a stock</option>
          {options.map((option) => (
            <option key={option.symbol} value={option.symbol}>
              {option.label}
            </option>
          ))}
          {value && !options.some((option) => option.symbol === value) && (
            <option value={value}>{value}</option>
          )}
        </select>
      </div>
      <div className="min-w-[220px]">
        <label className="label">Or type a symbol</label>
        <div className="flex gap-2">
          <input
            className="input-field"
            value={manual}
            onChange={(event) => setManual(event.target.value.toUpperCase())}
            placeholder="TATASTEEL.NS"
            disabled={disabled}
          />
          <button
            type="button"
            className="btn-secondary"
            disabled={disabled || !manual.trim()}
            onClick={() => onChange(manual.trim())}
          >
            Use
          </button>
        </div>
      </div>
    </div>
  );
};

export const JobNotice = ({ job, error }) => {
  if (!job && !error) return null;
  return (
    <div
      className={`rounded-lg border p-4 text-sm ${
        error
          ? "border-rose-200 bg-rose-50 text-rose-700"
          : "border-blue-200 bg-blue-50 text-blue-700"
      }`}
    >
      {error}
      {!error && job && (
        <span>
          Background job {job.job_id?.slice(0, 8)}:{" "}
          <span className="font-semibold">{job.status}</span>
          {job.status === "failed" && job.error ? ` — ${job.error}` : ""}
        </span>
      )}
    </div>
  );
};

export const EmptyState = ({ title, message }) => (
  <div className="bg-white rounded-xl shadow-md p-10 text-center">
    <p className="text-lg font-semibold text-gray-700">{title}</p>
    <p className="text-sm text-gray-500 mt-2">{message}</p>
  </div>
);

export const Section = ({ title, subtitle, children, actions }) => (
  <section className="bg-white rounded-xl shadow-md p-5 md:p-6">
    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between mb-4">
      <div>
        <h3 className="text-lg font-bold text-gray-800">{title}</h3>
        {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
      </div>
      {actions}
    </div>
    {children}
  </section>
);

export const SimpleTable = ({ columns, rows, empty = "No rows." }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm">
      <thead>
        <tr className="bg-gray-50">
          {columns.map((column) => (
            <th
              key={column.key}
              className={`px-3 py-2 font-semibold text-gray-600 whitespace-nowrap ${
                column.align === "center"
                  ? "text-center"
                  : column.align === "right"
                  ? "text-right"
                  : "text-left"
              }`}
            >
              {column.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 && (
          <tr>
            <td colSpan={columns.length} className="px-3 py-6 text-center text-gray-400">
              {empty}
            </td>
          </tr>
        )}
        {rows.map((row, index) => (
          <tr key={row.key ?? index} className="border-t hover:bg-gray-50">
            {columns.map((column) => (
              <td
                key={column.key}
                className={`px-3 py-2 align-top ${
                  column.align === "center"
                    ? "text-center"
                    : column.align === "right"
                    ? "text-right"
                    : "text-left"
                }`}
              >
                {column.render ? column.render(row) : row[column.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export const WarningList = ({ warnings }) => {
  if (!warnings?.length) return null;
  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
      <p className="text-sm font-semibold text-amber-800">Methodology warnings</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-amber-800">
        {warnings.map((warning, index) => (
          <li key={index}>{warning}</li>
        ))}
      </ul>
    </div>
  );
};
