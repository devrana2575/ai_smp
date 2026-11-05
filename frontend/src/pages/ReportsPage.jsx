import { useState, useEffect } from "react";
import { predictionService } from "../services/predictionService";
import { companyService } from "../services/companyService";
import Loading from "../components/common/Loading";
import toast from "react-hot-toast";
import { format } from "date-fns";

const ReportsPage = () => {
  const [companies, setCompanies] = useState([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [reportType, setReportType] = useState("predictions");
  const [predictions, setPredictions] = useState([]);
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
    } catch {
      toast.error("Failed to load companies");
    } finally {
      setInitialLoading(false);
    }
  };

  const loadReport = async () => {
    if (!selectedSymbol) return;
    setLoading(true);
    try {
      if (reportType === "predictions") {
        const data = await predictionService.getHistory(selectedSymbol);
        setPredictions(data);
        setEvaluation(null);
      } else {
        const data = await predictionService.getEvaluation(selectedSymbol);
        setEvaluation(data);
        setPredictions([]);
      }
    } catch {
      toast.error("Failed to load report");
    } finally {
      setLoading(false);
    }
  };

  const exportCSV = () => {
    if (predictions.length === 0) {
      toast.error("No data to export");
      return;
    }
    const headers = ["Date", "Symbol", "Company", "Current Price", "Predicted Price", "Signal"];
    const rows = predictions.map((p) => [
      p.createdAt ? format(new Date(p.createdAt), "yyyy-MM-dd") : "N/A",
      p.symbol,
      p.companyName,
      p.currentPrice,
      p.predictedPrice,
      p.signal,
    ]);
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedSymbol}_predictions_${format(new Date(), "yyyyMMdd")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("CSV exported!");
  };

  const metrics = evaluation?.evaluation || {};
  const bestModel = evaluation?.best_model;

  if (initialLoading) return <Loading message="Loading..." />;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-800">Reports</h2>
        <p className="text-sm text-gray-500">View prediction history and model performance reports</p>
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
          <div className="flex-1">
            <label className="label">Report Type</label>
            <select className="input-field" value={reportType} onChange={(e) => setReportType(e.target.value)}>
              <option value="predictions">Prediction History</option>
              <option value="performance">Model Performance</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button onClick={loadReport} disabled={loading || !selectedSymbol} className="btn-primary">
              {loading ? "Loading..." : "Generate Report"}
            </button>
            {reportType === "predictions" && predictions.length > 0 && (
              <button onClick={exportCSV} className="btn-secondary">
                Export CSV
              </button>
            )}
          </div>
        </div>
      </div>

      {loading && <Loading message="Generating report..." />}

      {reportType === "predictions" && predictions.length > 0 && !loading && (
        <div className="bg-white rounded-xl shadow-md p-6">
          <h3 className="text-lg font-bold text-gray-800 mb-4">Prediction History ({predictions.length} records)</h3>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50">
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Date</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Symbol</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Company</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">Current (₹)</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">Predicted (₹)</th>
                  <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">Signal</th>
                </tr>
              </thead>
              <tbody>
                {predictions.map((pred) => (
                  <tr key={pred._id} className="border-t hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm">{pred.createdAt ? format(new Date(pred.createdAt), "MMM dd, yyyy HH:mm") : "N/A"}</td>
                    <td className="px-4 py-3 font-mono text-sm">{pred.symbol}</td>
                    <td className="px-4 py-3 text-sm">{pred.companyName}</td>
                    <td className="px-4 py-3 text-center text-sm">₹{pred.currentPrice?.toFixed(2)}</td>
                    <td className="px-4 py-3 text-center text-sm font-medium">₹{pred.predictedPrice?.toFixed(2)}</td>
                    <td className="px-4 py-3 text-center">
                      <span className={`text-xs font-bold px-2 py-1 rounded ${
                        pred.signal === "BUY" ? "bg-green-100 text-green-700" :
                        pred.signal === "SELL" ? "bg-red-100 text-red-700" :
                        "bg-yellow-100 text-yellow-700"
                      }`}>
                        {pred.signal}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {reportType === "performance" && evaluation && !loading && (
        <>
          <div className="bg-white rounded-xl shadow-md p-6">
            <h3 className="text-lg font-bold text-gray-800 mb-4">Model Performance Report</h3>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-600">Model</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">MAE</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">MSE</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">RMSE</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">R² Score</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">MAPE</th>
                    <th className="px-4 py-3 text-center text-sm font-semibold text-gray-600">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(metrics).map(([name, m]) => (
                    <tr key={name} className={`border-t ${name === bestModel ? "bg-green-50" : "hover:bg-gray-50"}`}>
                      <td className="px-4 py-3 font-medium capitalize text-sm">{name.replace("_", " ")}</td>
                      <td className="px-4 py-3 text-center text-sm">{m.mae.toFixed(4)}</td>
                      <td className="px-4 py-3 text-center text-sm">{m.mse.toFixed(4)}</td>
                      <td className="px-4 py-3 text-center text-sm">{m.rmse.toFixed(4)}</td>
                      <td className="px-4 py-3 text-center text-sm font-bold">{m.r2_score.toFixed(4)}</td>
                      <td className="px-4 py-3 text-center text-sm">{m.mape.toFixed(2)}%</td>
                      <td className="px-4 py-3 text-center">
                        {name === bestModel && (
                          <span className="bg-green-100 text-green-800 px-2 py-1 rounded text-xs font-medium">Best</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-6 text-white">
              <p className="text-sm opacity-90">Best Model</p>
              <p className="text-2xl font-bold mt-1">{bestModel?.replace("_", " ")?.toUpperCase()}</p>
              <p className="text-xs opacity-75 mt-1">R²: {metrics[bestModel]?.r2_score.toFixed(4)}</p>
            </div>
            <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-6 text-white">
              <p className="text-sm opacity-90">Ensemble R² Score</p>
              <p className="text-2xl font-bold mt-1">{evaluation.ensemble_r2?.toFixed(4)}</p>
              <p className="text-xs opacity-75 mt-1">Average across all models</p>
            </div>
          </div>
        </>
      )}

      {!loading && !predictions.length && !evaluation && (
        <div className="bg-white rounded-xl shadow-md p-12 text-center">
          <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <p className="text-gray-500">Select a company and click Generate Report</p>
        </div>
      )}
    </div>
  );
};

export default ReportsPage;
