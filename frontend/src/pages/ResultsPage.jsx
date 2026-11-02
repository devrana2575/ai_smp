import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { format } from "date-fns";
import { predictionService } from "../services/predictionService";
import Loading from "../components/common/Loading";
import toast from "react-hot-toast";

const ALGORITHM_LABELS = {
  ensemble: "Ensemble (All 5 Models)",
  linear_regression: "Linear Regression",
  decision_tree: "Decision Tree",
  random_forest: "Random Forest",
  svr: "Support Vector Regressor (SVR)",
  xgboost: "XGBoost",
};

const formatMoney = (value) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "N/A"
    : `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

const formatDate = (value, pattern = "MMM dd, yyyy • hh:mm a") => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "N/A" : format(parsed, pattern);
};

const getAlgorithmLabel = (value) =>
  ALGORITHM_LABELS[value] || (value ? value.replace(/_/g, " ") : ALGORITHM_LABELS.ensemble);

const ResultsPage = () => {
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedPrediction, setSelectedPrediction] = useState(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await predictionService.getHistory();
      setPredictions(Array.isArray(data) ? data : []);
    } catch (err) {
      const message = err.response?.data?.detail || "Failed to load prediction results";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  const filteredPredictions = predictions.filter((prediction) => {
    const term = searchTerm.toLowerCase();
    return (
      (prediction.companyName || "").toLowerCase().includes(term) ||
      (prediction.symbol || "").toLowerCase().includes(term) ||
      getAlgorithmLabel(prediction.algorithm).toLowerCase().includes(term)
    );
  });

  const selectedChangePct =
    selectedPrediction?.currentPrice && selectedPrediction?.predictedPrice
      ? ((selectedPrediction.predictedPrice - selectedPrediction.currentPrice) /
          selectedPrediction.currentPrice) *
        100
      : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Results</h2>
          <p className="text-sm text-gray-500">
            Review previously generated predictions and inspect their details
          </p>
        </div>
        <button
          type="button"
          onClick={loadHistory}
          disabled={loading}
          className="btn-secondary text-sm self-start sm:self-auto disabled:opacity-60"
        >
          {loading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-md p-4">
        <div className="flex flex-col md:flex-row gap-4 md:items-center md:justify-between">
          <div className="relative flex-1">
            <svg className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search by company, symbol or algorithm..."
              className="input-field pl-10"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <p className="text-sm text-gray-500 whitespace-nowrap">
            {filteredPredictions.length} of {predictions.length} predictions
          </p>
        </div>
      </div>

      {loading ? (
        <Loading message="Loading prediction results..." />
      ) : error ? (
        <div className="bg-white rounded-xl shadow-md p-12 text-center">
          <p className="text-red-600 font-medium">{error}</p>
          <button onClick={loadHistory} className="mt-3 btn-primary">
            Retry
          </button>
        </div>
      ) : filteredPredictions.length === 0 ? (
        <div className="bg-white rounded-xl shadow-md p-12 text-center">
          <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
          </svg>
          <p className="text-gray-500">
            {predictions.length === 0 ? "No predictions have been generated yet." : "No predictions match your search."}
          </p>
          {predictions.length === 0 && (
            <Link to="/predict" className="inline-block mt-4 btn-primary">
              Generate a Prediction
            </Link>
          )}
        </div>
      ) : (
        <>
          <div className="hidden md:block bg-white rounded-xl shadow-md overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px]">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Company</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Symbol</th>
                    <th className="px-5 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wide">Predicted Price</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Prediction Date</th>
                    <th className="px-5 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Algorithm</th>
                    <th className="px-5 py-3 text-right text-xs font-semibold text-gray-600 uppercase tracking-wide">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPredictions.map((prediction) => (
                    <tr key={prediction._id} className="border-t hover:bg-gray-50">
                      <td className="px-5 py-3 text-sm font-medium text-gray-800">
                        {prediction.companyName || "N/A"}
                      </td>
                      <td className="px-5 py-3 text-sm font-mono text-blue-600">{prediction.symbol}</td>
                      <td className="px-5 py-3 text-sm font-semibold text-gray-800 text-right">
                        {formatMoney(prediction.predictedPrice)}
                      </td>
                      <td className="px-5 py-3 text-sm text-gray-600">
                        {formatDate(prediction.createdAt)}
                      </td>
                      <td className="px-5 py-3 text-sm text-gray-700">
                        {getAlgorithmLabel(prediction.algorithm)}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => setSelectedPrediction(prediction)}
                          className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
                        >
                          View Details
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="md:hidden space-y-3">
            {filteredPredictions.map((prediction) => (
              <div key={prediction._id} className="bg-white rounded-xl shadow-md p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-gray-800 truncate">
                      {prediction.companyName || "N/A"}
                    </p>
                    <p className="text-sm font-mono text-blue-600">{prediction.symbol}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-gray-500">Predicted</p>
                    <p className="font-bold text-gray-800">{formatMoney(prediction.predictedPrice)}</p>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <p className="text-gray-500">Date</p>
                    <p className="text-gray-700">{formatDate(prediction.createdAt, "MMM dd, yyyy")}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Algorithm</p>
                    <p className="text-gray-700">{getAlgorithmLabel(prediction.algorithm)}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSelectedPrediction(prediction)}
                  className="w-full btn-secondary text-sm"
                >
                  View Details
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {selectedPrediction && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50"
          onClick={() => setSelectedPrediction(null)}
        >
          <div
            className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 bg-white border-b px-5 md:px-6 py-4 flex items-start justify-between gap-4">
              <div>
                <h3 className="text-lg font-bold text-gray-800">
                  {selectedPrediction.companyName || "Prediction Details"}
                </h3>
                <p className="text-sm text-gray-500">
                  <span className="font-mono text-blue-600">{selectedPrediction.symbol}</span>
                  {" • "}
                  {getAlgorithmLabel(selectedPrediction.algorithm)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedPrediction(null)}
                className="w-9 h-9 flex items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100"
                aria-label="Close details"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-5 md:p-6 space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">Current Price</p>
                  <p className="text-lg font-bold text-gray-800 mt-1">
                    {formatMoney(selectedPrediction.currentPrice)}
                  </p>
                </div>
                <div className="bg-green-50 rounded-lg p-3">
                  <p className="text-xs text-green-700">Predicted Price</p>
                  <p className="text-lg font-bold text-green-700 mt-1">
                    {formatMoney(selectedPrediction.predictedPrice)}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">Expected Change</p>
                  <p
                    className={`text-lg font-bold mt-1 ${
                      selectedChangePct === null
                        ? "text-gray-800"
                        : selectedChangePct >= 0
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                  >
                    {selectedChangePct === null
                      ? "N/A"
                      : `${selectedChangePct >= 0 ? "+" : ""}${selectedChangePct.toFixed(2)}%`}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">Signal</p>
                  <span
                    className={`inline-block mt-1 text-xs font-bold px-2 py-1 rounded ${
                      selectedPrediction.signal === "BUY"
                        ? "bg-green-100 text-green-700"
                        : selectedPrediction.signal === "SELL"
                        ? "bg-red-100 text-red-700"
                        : "bg-yellow-100 text-yellow-700"
                    }`}
                  >
                    {selectedPrediction.signal || "N/A"}
                  </span>
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Prediction Information</h4>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
                  <div className="flex justify-between gap-3">
                    <dt className="text-gray-500">Company</dt>
                    <dd className="font-medium text-gray-800 text-right">
                      {selectedPrediction.companyName || "N/A"}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-gray-500">Stock Symbol</dt>
                    <dd className="font-mono font-medium text-blue-600 text-right">
                      {selectedPrediction.symbol}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-gray-500">Selected Algorithm</dt>
                    <dd className="font-medium text-gray-800 text-right">
                      {getAlgorithmLabel(selectedPrediction.algorithm)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-gray-500">Prediction Date</dt>
                    <dd className="font-medium text-gray-800 text-right">
                      {formatDate(selectedPrediction.createdAt)}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-3">
                    <dt className="text-gray-500">Ensemble Prediction</dt>
                    <dd className="font-medium text-gray-800 text-right">
                      {formatMoney(selectedPrediction.ensemblePrediction)}
                    </dd>
                  </div>
                </dl>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-3">Algorithm Breakdown</h4>
                {selectedPrediction.models &&
                Object.keys(selectedPrediction.models).length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[480px]">
                      <thead>
                        <tr className="bg-gray-50">
                          <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase">Algorithm</th>
                          <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600 uppercase">Predicted Price</th>
                          <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600 uppercase">R²</th>
                          <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600 uppercase">MAE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(selectedPrediction.models).map(([name, model]) => (
                          <tr
                            key={name}
                            className={`border-t ${
                              selectedPrediction.algorithm === name ? "bg-blue-50" : ""
                            }`}
                          >
                            <td className="px-4 py-2 text-sm text-gray-800">
                              {ALGORITHM_LABELS[name] || name.replace(/_/g, " ")}
                              {selectedPrediction.algorithm === name && (
                                <span className="ml-2 text-xs font-medium text-blue-600">Selected</span>
                              )}
                            </td>
                            <td className="px-4 py-2 text-sm text-right font-medium text-gray-800">
                              {formatMoney(model?.prediction)}
                            </td>
                            <td className="px-4 py-2 text-sm text-right text-gray-600">
                              {model?.r2_score !== undefined ? Number(model.r2_score).toFixed(4) : "—"}
                            </td>
                            <td className="px-4 py-2 text-sm text-right text-gray-600">
                              {model?.mae !== undefined ? Number(model.mae).toFixed(4) : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No model breakdown is available for this prediction.</p>
                )}
              </div>

              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                <Link
                  to={`/stock/${selectedPrediction.symbol}`}
                  className="btn-secondary text-center"
                  onClick={() => setSelectedPrediction(null)}
                >
                  View Historical Data
                </Link>
                <Link
                  to={`/predict?symbol=${selectedPrediction.symbol}`}
                  className="btn-primary text-center"
                  onClick={() => setSelectedPrediction(null)}
                >
                  Run New Prediction
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsPage;
