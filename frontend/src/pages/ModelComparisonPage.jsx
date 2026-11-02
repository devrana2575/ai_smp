import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend,
} from "recharts";
import { predictionService } from "../services/predictionService";
import Loading from "../components/common/Loading";
import toast from "react-hot-toast";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

const ModelComparisonPage = () => {
  const { symbol } = useParams();
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadComparison();
  }, [symbol]);

  const loadComparison = async () => {
    try {
      const data = await predictionService.getComparison(symbol);
      setComparison(data);
    } catch (error) {
      toast.error("Failed to load comparison data");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Loading message="Loading model comparison..." />;

  const evaluation = comparison?.evaluation?.evaluation || {};
  const bestModel = comparison?.evaluation?.best_model;

  const metricsData = Object.entries(evaluation).map(([name, metrics], index) => ({
    name: name.replace("_", " ").toUpperCase(),
    r2: metrics.r2_score,
    mae: metrics.mae,
    rmse: metrics.rmse,
    fill: COLORS[index % COLORS.length],
  }));

  const radarData = Object.entries(evaluation).map(([name, metrics]) => ({
    model: name.replace("_", " ").toUpperCase(),
    accuracy: metrics.r2_score * 100,
    precision: Math.max(0, 100 - metrics.mae),
    speed: Math.max(0, 100 - metrics.rmse),
  }));

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">Model Comparison: {symbol}</h1>
          <p className="text-gray-500">Detailed evaluation of all 5 ML models</p>
        </div>
        <div className="flex gap-3">
          <Link to={`/predict/${symbol}`} className="btn-primary">
            Run Prediction
          </Link>
          <Link to={`/stock/${symbol}`} className="btn-secondary">
            Back to Stock
          </Link>
        </div>
      </div>

      <div className="card mb-8">
        <h2 className="text-xl font-bold text-gray-800 mb-4">R² Score Comparison</h2>
        <ResponsiveContainer width="100%" height={350}>
          <BarChart data={metricsData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 1]} />
            <Tooltip formatter={(value) => [value.toFixed(4), "R² Score"]} />
            <Bar dataKey="r2" radius={[8, 8, 0, 0]}>
              {metricsData.map((entry, index) => (
                <Cell key={index} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="card">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Error Metrics (Lower is Better)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={metricsData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="mae" fill="#ef4444" name="MAE" radius={[4, 4, 0, 0]} />
              <Bar dataKey="rmse" fill="#f59e0b" name="RMSE" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Model Performance Radar</h2>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="model" tick={{ fontSize: 10 }} />
              <PolarRadiusAxis angle={30} domain={[0, 100]} />
              <Radar name="Accuracy" dataKey="accuracy" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
              <Radar name="Precision" dataKey="precision" stroke="#10b981" fill="#10b981" fillOpacity={0.3} />
              <Legend />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h2 className="text-xl font-bold text-gray-800 mb-4">Detailed Metrics Table</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="bg-gray-50">
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Model</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">MAE</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">MSE</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">RMSE</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">R² Score</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">MAPE (%)</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">Status</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(evaluation).map(([name, metrics], index) => (
                <tr key={name} className={`border-t ${name === bestModel ? "bg-green-50" : ""}`}>
                  <td className="px-4 py-3 font-medium capitalize flex items-center gap-2">
                    <div className="w-3 h-3 rounded" style={{ backgroundColor: COLORS[index] }}></div>
                    {name.replace("_", " ")}
                  </td>
                  <td className="px-4 py-3 text-center">{metrics.mae.toFixed(4)}</td>
                  <td className="px-4 py-3 text-center">{metrics.mse.toFixed(4)}</td>
                  <td className="px-4 py-3 text-center">{metrics.rmse.toFixed(4)}</td>
                  <td className="px-4 py-3 text-center font-bold">{metrics.r2_score.toFixed(4)}</td>
                  <td className="px-4 py-3 text-center">{metrics.mape.toFixed(2)}%</td>
                  <td className="px-4 py-3 text-center">
                    {name === bestModel ? (
                      <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-sm font-medium">
                        Best
                      </span>
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 p-4 bg-blue-50 rounded-lg">
          <p className="text-blue-800">
            <strong>Best Model:</strong> {bestModel?.replace("_", " ").toUpperCase()} with R² Score of{" "}
            {evaluation[bestModel]?.r2_score.toFixed(4)}
          </p>
          <p className="text-blue-600 text-sm mt-1">
            Ensemble R² Score: {comparison?.evaluation?.ensemble_r2?.toFixed(4)}
          </p>
        </div>
      </div>
    </div>
  );
};

export default ModelComparisonPage;
