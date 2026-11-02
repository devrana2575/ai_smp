import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Legend,
} from "recharts";
import { predictionService } from "../services/predictionService";
import { companyService } from "../services/companyService";
import Loading from "../components/common/Loading";
import toast from "react-hot-toast";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

const ComparisonPage = () => {
  const [companies, setCompanies] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);

  useEffect(() => {
    loadCompanies();
  }, []);

  const loadCompanies = async () => {
    try {
      const data = await companyService.getAll();
      setCompanies(data);
    } catch (error) {
      toast.error("Failed to load companies");
    } finally {
      setInitialLoading(false);
    }
  };

  const loadEvaluation = async () => {
    if (!selectedSymbol) return;
    setLoading(true);
    try {
      const data = await predictionService.getEvaluation(selectedSymbol);
      setEvaluation(data);
    } catch (error) {
      toast.error("Failed to load evaluation. Train models first.");
    } finally {
      setLoading(false);
    }
  };

  const metrics = evaluation?.evaluation || {};
  const bestModel = evaluation?.best_model;

  const metricsData = Object.entries(metrics).map(([name, m], i) => ({
    name: name.replace("_", " ").toUpperCase(),
    r2: m.r2_score,
    mae: m.mae,
    rmse: m.rmse,
    fill: COLORS[i % COLORS.length],
  }));

  const radarData = Object.entries(metrics).map(([name, m]) => ({
    model: name.replace("_", " ").toUpperCase(),
    accuracy: m.r2_score * 100,
    precision: Math.max(0, 100 - m.mae),
  }));

  if (initialLoading) return <Loading message="Loading..." />;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-800">Algorithm Comparison</h2>
        <p className="text-sm text-gray-500">Compare performance of all 5 ML models</p>
      </div>

      <div className="bg-white rounded-xl shadow-md p-6">
        <div className="flex flex-col md:flex-row gap-4 items-end">
          <div className="flex-1">
            <label className="label">Select Company</label>
            <select className="input-field" value={selectedSymbol} onChange={(e) => setSelectedSymbol(e.target.value)}>
              <option value="">-- Select a company --</option>
              {companies.map((c) => (
                <option key={c._id} value={c.symbol}>{c.name} ({c.symbol})</option>
              ))}
            </select>
          </div>
          <button onClick={loadEvaluation} disabled={loading || !selectedSymbol} className="btn-primary">
            {loading ? "Loading..." : "Load Comparison"}
          </button>
        </div>
      </div>

      {evaluation && (
        <>
          <div className="bg-white rounded-xl shadow-md p-6">
            <h3 className="text-lg font-bold text-gray-800 mb-4">R² Score Comparison</h3>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={metricsData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
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

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">Error Metrics (Lower is Better)</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={metricsData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis />
                  <Tooltip />
                  <Bar dataKey="mae" fill="#ef4444" name="MAE" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="rmse" fill="#f59e0b" name="RMSE" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white rounded-xl shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">Performance Radar</h3>
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

          {bestModel && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <p className="text-blue-800 font-medium">
                Best Model: <span className="font-bold">{bestModel.replace("_", " ").toUpperCase()}</span>
                {" "}with R² Score of {metrics[bestModel]?.r2_score.toFixed(4)}
              </p>
              <p className="text-blue-600 text-sm mt-1">
                Ensemble R² Score: {evaluation.ensemble_r2?.toFixed(4)}
              </p>
            </div>
          )}
        </>
      )}

      {!evaluation && !loading && (
        <div className="bg-white rounded-xl shadow-md p-12 text-center">
          <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17V7m0 10a2 2 0 01-2 2H5a2 2 0 01-2-2V7a2 2 0 012-2h2a2 2 0 012 2m0 10a2 2 0 002 2h2a2 2 0 002-2M9 7a2 2 0 012-2h2a2 2 0 012 2m0 10V7m0 10a2 2 0 002 2h2a2 2 0 002-2V7a2 2 0 00-2-2h-2a2 2 0 00-2 2" />
          </svg>
          <p className="text-gray-500">Select a company and click Load Comparison to see results</p>
        </div>
      )}
    </div>
  );
};

export default ComparisonPage;
