import { useEffect, useState } from "react";
import { predictionService } from "../../services/predictionService";

const REGIME_STYLES = {
  bull: {
    badge: "bg-green-100 text-green-800",
    accent: "text-green-600",
    panel: "border-green-200 bg-green-50",
    arrow: "M5 15l7-7 7 7",
  },
  bear: {
    badge: "bg-red-100 text-red-800",
    accent: "text-red-600",
    panel: "border-red-200 bg-red-50",
    arrow: "M19 9l-7 7-7-7",
  },
  neutral: {
    badge: "bg-gray-100 text-gray-700",
    accent: "text-gray-500",
    panel: "border-gray-200 bg-gray-50",
    arrow: "M5 12h14",
  },
};

const formatNumber = (value) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "N/A"
    : Number(value).toLocaleString("en-IN", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });

const formatPercent = (value) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "N/A"
    : `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(2)}%`;

const Metric = ({ label, value, valueClassName = "text-gray-800" }) => (
  <div className="rounded-lg border border-gray-200 bg-white p-3">
    <p className="text-xs text-gray-500">{label}</p>
    <p className={`mt-1 text-sm font-bold ${valueClassName}`}>{value}</p>
  </div>
);

const MarketRegimeCard = ({ symbol }) => {
  const [regime, setRegime] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    if (!symbol) return undefined;

    setLoading(true);
    setError(null);
    predictionService
      .getMarketRegime(symbol)
      .then((data) => {
        if (active) setRegime(data);
      })
      .catch((err) => {
        if (active) {
          setRegime(null);
          setError(
            err?.response?.data?.detail ||
              err?.message ||
              "Market regime is unavailable."
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [symbol]);

  const style = REGIME_STYLES[regime?.regime] || REGIME_STYLES.neutral;
  const metrics = regime?.metrics || {};
  const return60 = metrics.return_60d_pct;
  const returnClass =
    return60 === null || return60 === undefined
      ? "text-gray-800"
      : return60 >= 0
        ? "text-green-600"
        : "text-red-600";

  return (
    <div className={`rounded-xl border shadow-md p-4 md:p-5 ${style.panel}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base md:text-lg font-bold text-gray-800">
              Market regime
            </h3>
            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold ${style.badge}`}>
              {loading ? "Checking..." : regime?.label || "Neutral"}
            </span>
          </div>
          <p className="mt-1 text-xs text-gray-600">
            {loading
              ? "Classifying the latest 50/200-session trend and 60-session momentum."
              : error || regime?.reason}
          </p>
        </div>
        <div className={`inline-flex items-center gap-1.5 text-sm font-semibold ${style.accent}`}>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={style.arrow} />
          </svg>
          {loading ? "Loading" : regime?.as_of ? `As of ${regime.as_of}` : "No date"}
        </div>
      </div>

      {loading ? (
        <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-16 animate-pulse rounded-lg bg-gray-200" />
          ))}
        </div>
      ) : error ? (
        <p className="mt-4 rounded-lg border border-gray-200 bg-white p-3 text-xs text-gray-500">
          The regime indicator could not be loaded. Stock data and predictions are unaffected.
        </p>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 lg:grid-cols-4 gap-3">
            <Metric label="Latest close" value={formatNumber(metrics.latest_close)} />
            <Metric label="50-session average" value={formatNumber(metrics.sma_50)} />
            <Metric label="200-session average" value={formatNumber(metrics.sma_200)} />
            <Metric
              label="60-session return"
              value={formatPercent(metrics.return_60d_pct)}
              valueClassName={returnClass}
            />
          </div>
          <p className="mt-3 text-xs text-gray-500">
            {regime?.disclaimer} Classification uses {regime?.data_points} historical sessions.
          </p>
        </>
      )}
    </div>
  );
};

export default MarketRegimeCard;
