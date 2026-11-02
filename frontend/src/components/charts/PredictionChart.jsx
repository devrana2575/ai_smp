import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { format } from "date-fns";

const formatPrice = (value) =>
  Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });

const PredictionChart = ({ data = [], predictedPrice }) => {
  const history = data.map((row) => {
    const parsed = new Date(row.Date);
    return {
      date: Number.isNaN(parsed.getTime()) ? "N/A" : format(parsed, "MMM dd"),
      fullDate: Number.isNaN(parsed.getTime()) ? "N/A" : format(parsed, "MMM dd, yyyy"),
      actual: row.Close,
      predicted: null,
    };
  });

  if (!history.length || predictedPrice === null || predictedPrice === undefined) {
    return (
      <div className="h-[300px] flex items-center justify-center text-sm text-gray-500">
        Prediction graph is unavailable because historical data could not be loaded.
      </div>
    );
  }

  const lastIndex = history.length - 1;
  history[lastIndex].predicted = history[lastIndex].actual;
  history.push({
    date: "Next Day",
    fullDate: "Predicted next trading day",
    actual: null,
    predicted: predictedPrice,
  });

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={history} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" minTickGap={24} />
        <YAxis
          domain={["auto", "auto"]}
          tick={{ fontSize: 11 }}
          tickFormatter={formatPrice}
          width={70}
        />
        <Tooltip
          formatter={(value, name) => [
            value === null || value === undefined ? "N/A" : `₹${formatPrice(value)}`,
            name,
          ]}
          labelFormatter={(label, payload) => payload?.[0]?.payload?.fullDate || label}
          contentStyle={{ borderRadius: "8px", border: "none", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="actual"
          name="Historical Close"
          stroke="#2563eb"
          strokeWidth={2}
          dot={false}
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="predicted"
          name="Predicted Price"
          stroke="#10b981"
          strokeWidth={2}
          strokeDasharray="5 4"
          dot={{ r: 4 }}
          activeDot={{ r: 6 }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default PredictionChart;
