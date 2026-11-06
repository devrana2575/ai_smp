import { useCallback, useEffect, useState } from "react";
import { format } from "date-fns";
import StockChart from "../charts/StockChart";
import MarketRegimeCard from "./MarketRegimeCard";
import { predictionService } from "../../services/predictionService";

const PERIODS = [
  { label: "1 Month", value: "1mo" },
  { label: "3 Months", value: "3mo" },
  { label: "6 Months", value: "6mo" },
  { label: "1 Year", value: "1y" },
];

const formatNumber = (value) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "N/A"
    : Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });

const formatMoney = (value) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "N/A"
    : `₹${formatNumber(value)}`;

const formatVolume = (value) =>
  value === null || value === undefined ? "N/A" : Number(value).toLocaleString("en-IN");

const safeDate = (value, pattern = "MMM dd, yyyy") => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "N/A" : format(parsed, pattern);
};

const StockDataPanel = ({ symbol, company = null, actions = null, onClear = null }) => {
  const [period, setPeriod] = useState("1mo");
  const [stockData, setStockData] = useState([]);
  const [stockInfo, setStockInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadStock = useCallback(async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);

    try {
      const result = await predictionService.getStockData(symbol, period);
      if (Array.isArray(result?.data)) {
        setStockData(result.data);
      } else {
        setStockData([]);
        setError("No stock data returned for this company.");
      }
    } catch (err) {
      setStockData([]);
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          "Failed to load stock data. Make sure the AI service is running."
      );
    } finally {
      setLoading(false);
    }
  }, [symbol, period]);

  useEffect(() => {
    loadStock();
  }, [loadStock]);

  useEffect(() => {
    let active = true;
    if (!symbol) {
      setStockInfo(null);
      return undefined;
    }

    predictionService
      .getStockInfo(symbol)
      .then((info) => {
        if (active) setStockInfo(info);
      })
      .catch(() => {
        if (active) setStockInfo(null);
      });

    return () => {
      active = false;
    };
  }, [symbol]);

  const latest = stockData.length ? stockData[stockData.length - 1] : null;
  const previous = stockData.length > 1 ? stockData[stockData.length - 2] : null;
  const change =
    latest && previous && previous.Close
      ? ((latest.Close - previous.Close) / previous.Close) * 100
      : null;
  const isPositive = change !== null && change >= 0;

  const chartData = stockData.map((row) => ({
    date: safeDate(row.Date, "MMM dd"),
    fullDate: safeDate(row.Date),
    Close: row.Close,
  }));

  const recentRows = stockData.slice(-12).reverse();
  const displayName = company?.name || stockInfo?.name || symbol;
  const sector = stockInfo?.sector || company?.category;
  const industry = stockInfo?.industry || company?.subCategory;

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-md p-4 md:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg md:text-xl font-bold text-gray-800">{displayName}</h3>
              <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-xs font-mono font-semibold">
                {symbol}
              </span>
              {company?.category && (
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    company.category === "Metal"
                      ? "bg-blue-100 text-blue-700"
                      : "bg-orange-100 text-orange-700"
                  }`}
                >
                  {company.category}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-500 mt-1">
              {[sector, industry, company?.exchange].filter(Boolean).join(" • ") || "Metal & Mining"}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex rounded-lg bg-gray-100 p-1">
              {PERIODS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPeriod(option.value)}
                  className={`px-2.5 md:px-3 py-1.5 text-xs rounded-md font-medium transition ${
                    period === option.value
                      ? "bg-blue-600 text-white shadow-sm"
                      : "text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            {actions}
            {onClear && (
              <button type="button" onClick={onClear} className="btn-secondary text-sm">
                Clear
              </button>
            )}
          </div>
        </div>
      </div>

      <MarketRegimeCard symbol={symbol} />

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-3 md:gap-4">
        <div className="bg-white rounded-xl shadow-md p-4">
          <p className="text-xs text-gray-500">Open</p>
          <p className="text-lg md:text-xl font-bold text-gray-800 mt-1">
            {formatMoney(latest?.Open)}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-4">
          <p className="text-xs text-gray-500">High</p>
          <p className="text-lg md:text-xl font-bold text-green-600 mt-1">
            {formatMoney(latest?.High)}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-4">
          <p className="text-xs text-gray-500">Low</p>
          <p className="text-lg md:text-xl font-bold text-red-600 mt-1">
            {formatMoney(latest?.Low)}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-4">
          <p className="text-xs text-gray-500">Close</p>
          <p className="text-lg md:text-xl font-bold text-gray-800 mt-1">
            {formatMoney(latest?.Close)}
          </p>
        </div>
        <div className="bg-white rounded-xl shadow-md p-4 col-span-2 md:col-span-1">
          <p className="text-xs text-gray-500">Volume</p>
          <p className="text-lg md:text-xl font-bold text-gray-800 mt-1">
            {formatVolume(latest?.Volume)}
          </p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-md p-4 md:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-800">Historical Stock Price</h3>
            <p className="text-xs text-gray-500">
              {latest ? `Latest session: ${safeDate(latest.Date)}` : "Close price history"}
            </p>
          </div>
          {change !== null && (
            <span
              className={`inline-flex items-center gap-1 text-sm font-semibold ${
                isPositive ? "text-green-600" : "text-red-600"
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d={isPositive ? "M5 15l7-7 7 7" : "M19 9l-7 7-7-7"}
                />
              </svg>
              {isPositive ? "+" : ""}
              {change.toFixed(2)}% vs previous close
            </span>
          )}
        </div>
        <StockChart
          data={chartData}
          loading={loading}
          error={error}
          onRetry={loadStock}
          height={340}
        />
      </div>

      <div className="bg-white rounded-xl shadow-md p-4 md:p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-800">Recent Sessions</h3>
            <p className="text-xs text-gray-500">Open, High, Low, Close and Volume</p>
          </div>
        </div>
        {loading ? (
          <div className="py-10 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3"></div>
            <p className="text-sm text-gray-500">Loading historical data...</p>
          </div>
        ) : error ? (
          <div className="py-8 text-center text-sm text-gray-500">
            Historical data is unavailable.
          </div>
        ) : recentRows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead>
                <tr className="bg-gray-50">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Date</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wide">Open</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wide">High</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wide">Low</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wide">Close</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wide">Volume</th>
                </tr>
              </thead>
              <tbody>
                {recentRows.map((row) => (
                  <tr key={row.Date} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-700 whitespace-nowrap">{safeDate(row.Date)}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatMoney(row.Open)}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatMoney(row.High)}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatMoney(row.Low)}</td>
                    <td className="px-4 py-3 text-sm text-right font-semibold text-gray-800">{formatMoney(row.Close)}</td>
                    <td className="px-4 py-3 text-sm text-right text-gray-700">{formatVolume(row.Volume)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="py-8 text-center text-sm text-gray-500">No historical data available.</p>
        )}
      </div>
    </div>
  );
};

export default StockDataPanel;
