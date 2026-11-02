import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const formatPrice = (value) =>
  Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });

const StockChart = ({ data = [], loading = false, error = null, onRetry, height = 340 }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center" style={{ height }}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-9 w-9 border-b-2 border-blue-600 mx-auto mb-3"></div>
          <p className="text-sm text-gray-500">Loading stock price history...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center text-gray-500" style={{ height }}>
        <div className="text-center px-4">
          <svg className="w-12 h-12 mx-auto text-gray-300 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M5.07 19H18.93a2 2 0 001.74-3L13.74 4a2 2 0 00-3.48 0L3.33 16a2 2 0 001.74 3z" />
          </svg>
          <p className="text-sm">{error}</p>
          {onRetry && (
            <button onClick={onRetry} className="mt-3 text-sm text-blue-600 hover:underline">
              Retry
            </button>
          )}
        </div>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="flex items-center justify-center text-gray-400" style={{ height }}>
        No stock data available for this period.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="stockCloseGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#2563eb" stopOpacity={0.22} />
            <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" minTickGap={24} />
        <YAxis
          domain={["auto", "auto"]}
          tick={{ fontSize: 11 }}
          tickFormatter={formatPrice}
          width={70}
        />
        <Tooltip
          formatter={(value) => [`₹${formatPrice(value)}`, "Close"]}
          labelFormatter={(label, payload) => payload?.[0]?.payload?.fullDate || label}
          contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}
        />
        <Area
          type="monotone"
          dataKey="Close"
          stroke="#2563eb"
          strokeWidth={2}
          fill="url(#stockCloseGradient)"
          dot={false}
          activeDot={{ r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};

export default StockChart;
