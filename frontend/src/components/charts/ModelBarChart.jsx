import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

const ModelBarChart = ({ models }) => {
  if (!models || typeof models !== "object") return null;

  const data = Object.entries(models)
    .filter(([_, v]) => v && v.prediction !== null && v.prediction !== undefined)
    .map(([name, data], index) => ({
      name: name.replace("_", " ").toUpperCase(),
      prediction: data.prediction,
      fill: COLORS[index % COLORS.length],
    }));

  if (data.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-md p-6">
      <h3 className="text-lg font-bold text-gray-800 mb-4">Model Predictions</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(value) => [`₹${value}`, "Predicted Price"]} />
          <Bar dataKey="prediction" radius={[8, 8, 0, 0]}>
            {data.map((entry, index) => (
              <Cell key={index} fill={entry.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default ModelBarChart;
