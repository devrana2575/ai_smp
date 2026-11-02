import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { format } from "date-fns";
import ModelBarChart from "../components/charts/ModelBarChart";
import PredictionChart from "../components/charts/PredictionChart";
import Loading from "../components/common/Loading";
import { predictionService } from "../services/predictionService";
import { companyService } from "../services/companyService";
import toast from "react-hot-toast";

const ALGORITHM_OPTIONS = [
  { value: "ensemble", label: "Ensemble (All 5 Models)" },
  { value: "linear_regression", label: "Linear Regression" },
  { value: "decision_tree", label: "Decision Tree" },
  { value: "random_forest", label: "Random Forest" },
  { value: "svr", label: "Support Vector Regressor (SVR)" },
  { value: "xgboost", label: "XGBoost" },
];

const MODEL_LABELS = Object.fromEntries(
  ALGORITHM_OPTIONS.filter((option) => option.value !== "ensemble").map((option) => [
    option.value,
    option.label,
  ])
);

const formatMoney = (value) =>
  value === null || value === undefined || Number.isNaN(Number(value))
    ? "N/A"
    : `₹${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;

const formatDate = (value) => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "N/A" : format(parsed, "MMM dd, yyyy • hh:mm a");
};

const PredictionPage = () => {
  const { symbol: routeSymbol } = useParams();
  const [searchParams] = useSearchParams();
  const initialSymbol = searchParams.get("symbol") || routeSymbol || "";

  const [companies, setCompanies] = useState([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [companiesError, setCompaniesError] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState(initialSymbol);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState("ensemble");
  const [prediction, setPrediction] = useState(null);
  const [historyData, setHistoryData] = useState([]);
  const [historyError, setHistoryError] = useState(null);
  const [predictError, setPredictError] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [training, setTraining] = useState(false);

  const loadCompanies = useCallback(async () => {
    setCompaniesLoading(true);
    setCompaniesError(null);
    try {
      const data = await companyService.getAll();
      setCompanies(Array.isArray(data) ? data : []);
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to load companies";
      setCompaniesError(message);
      toast.error(message);
    } finally {
      setCompaniesLoading(false);
    }
  }, []);

  const refreshModelStatus = useCallback(async () => {
    if (!selectedSymbol) {
      setModelStatus(null);
      return;
    }
    try {
      const status = await predictionService.getModelStatus(selectedSymbol);
      setModelStatus(status);
    } catch (error) {
      setModelStatus(null);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    loadCompanies();
  }, [loadCompanies]);

  useEffect(() => {
    const paramSymbol = searchParams.get("symbol") || routeSymbol || "";
    if (paramSymbol) setSelectedSymbol(paramSymbol);
  }, [routeSymbol, searchParams]);

  useEffect(() => {
    setPrediction(null);
    setHistoryData([]);
    setHistoryError(null);
    setPredictError(null);
    setSelectedAlgorithm("ensemble");
    refreshModelStatus();
  }, [selectedSymbol, refreshModelStatus]);

  const handleTrain = async () => {
    if (!selectedSymbol) {
      toast.error("Please select a company first");
      return;
    }
    setTraining(true);
    try {
      await predictionService.train(selectedSymbol);
      toast.success("Models trained successfully!");
      await refreshModelStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Training failed");
    } finally {
      setTraining(false);
    }
  };

  const handlePredict = async () => {
    if (!selectedSymbol) {
      toast.error("Please select a company first");
      return;
    }

    setLoading(true);
    setPredictError(null);
    try {
      const result = await predictionService.predict(selectedSymbol, selectedAlgorithm);
      setPrediction(result);
      toast.success("Prediction generated successfully!");

      try {
        const stock = await predictionService.getStockData(selectedSymbol, "1mo");
        setHistoryData(Array.isArray(stock?.data) ? stock.data : []);
        setHistoryError(null);
      } catch (error) {
        setHistoryData([]);
        setHistoryError(
          error.response?.data?.detail ||
            "Historical data could not be loaded for the prediction graph."
        );
      }
    } catch (error) {
      const message =
        error.response?.data?.detail || error.message || "Prediction failed";
      setPredictError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const resetPrediction = () => {
    setPrediction(null);
    setHistoryData([]);
    setHistoryError(null);
    setPredictError(null);
  };

  const selectedCompany = companies.find((company) => company.symbol === selectedSymbol);
  const trainedCount = modelStatus
    ? Object.values(modelStatus.models || {}).filter(Boolean).length
    : 0;
  const algorithmLabel =
    ALGORITHM_OPTIONS.find(
      (option) => option.value === (prediction?.algorithm || selectedAlgorithm)
    )?.label || "Ensemble (All 5 Models)";

  const predictedPrice = prediction?.predictedPrice;
  const currentPrice = prediction?.currentPrice;
  const changePct =
    currentPrice && predictedPrice !== null && predictedPrice !== undefined
      ? ((predictedPrice - currentPrice) / currentPrice) * 100
      : null;
  const isPositive = changePct !== null && changePct >= 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Prediction</h2>
          <p className="text-sm text-gray-500">
            Select a company and generate a next-day price prediction using the existing ML models
          </p>
        </div>
        {prediction && (
          <button type="button" onClick={resetPrediction} className="btn-secondary text-sm self-start sm:self-auto">
            New Prediction
          </button>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-md p-4 md:p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="label">Select Company</label>
            <select
              className="input-field"
              value={selectedSymbol}
              onChange={(e) => setSelectedSymbol(e.target.value)}
              disabled={companiesLoading}
            >
              <option value="">
                {companiesLoading ? "Loading companies..." : "-- Select a company --"}
              </option>
              {companies.map((company) => (
                <option key={company._id} value={company.symbol}>
                  {company.name} ({company.symbol})
                </option>
              ))}
            </select>
            {companiesError && (
              <button
                type="button"
                onClick={loadCompanies}
                className="mt-2 text-xs text-blue-600 hover:underline"
              >
                Retry loading companies
              </button>
            )}
          </div>

          <div>
            <label className="label">Prediction Algorithm</label>
            <select
              className="input-field"
              value={selectedAlgorithm}
              onChange={(e) => setSelectedAlgorithm(e.target.value)}
              disabled={!!prediction || loading}
            >
              {ALGORITHM_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {prediction && (
              <p className="text-xs text-gray-500 mt-1">
                Start a new prediction to change the algorithm.
              </p>
            )}
          </div>

          <div className="flex flex-col justify-end">
            <label className="label">Model Status</label>
            <div
              className={`px-3 py-2 rounded-lg text-sm font-medium ${
                selectedSymbol
                  ? trainedCount === 5
                    ? "bg-green-50 text-green-700"
                    : "bg-yellow-50 text-yellow-700"
                  : "bg-gray-50 text-gray-500"
              }`}
            >
              {selectedSymbol
                ? modelStatus
                  ? `${trainedCount}/5 models trained`
                  : "Model status unavailable"
                : "Select a company to check models"}
            </div>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-3 mt-5">
          <button
            type="button"
            onClick={handleTrain}
            disabled={training || !selectedSymbol || loading}
            className="btn-primary disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {training ? "Training Models..." : "Train Models"}
          </button>
          <button
            type="button"
            onClick={handlePredict}
            disabled={loading || !selectedSymbol || !!prediction}
            className="bg-green-600 hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed text-white px-5 py-2 rounded-lg transition font-medium"
          >
            {loading ? "Predicting..." : "Predict Stock Price"}
          </button>
          {selectedCompany && (
            <Link
              to={`/stock/${selectedCompany.symbol}`}
              className="btn-secondary text-center"
            >
              View Historical Data
            </Link>
          )}
        </div>

        {predictError && (
          <div className="mt-4 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
            {predictError}
          </div>
        )}
      </div>

      {loading && <Loading message="Generating prediction using the trained models..." />}

      {!loading && !prediction && (
        <div className="bg-white rounded-xl shadow-md p-8 md:p-12 text-center">
          <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="text-gray-500">
            Select a company above, then click Predict Stock Price to generate a prediction.
          </p>
          <p className="text-xs text-gray-400 mt-2">
            The prediction graph will appear only after a successful prediction.
          </p>
        </div>
      )}

      {!loading && prediction && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-5 text-white">
              <p className="text-xs opacity-90">Current Price</p>
              <p className="text-2xl font-bold mt-1">{formatMoney(currentPrice)}</p>
              <p className="text-xs opacity-75 mt-1">{prediction.symbol}</p>
            </div>
            <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl p-5 text-white">
              <p className="text-xs opacity-90">Predicted Price</p>
              <p className="text-2xl font-bold mt-1">{formatMoney(predictedPrice)}</p>
              <p className="text-xs opacity-75 mt-1">{algorithmLabel}</p>
            </div>
            <div className="bg-white rounded-xl shadow-md p-5">
              <p className="text-xs text-gray-500">Expected Change</p>
              <p
                className={`text-2xl font-bold mt-1 ${
                  changePct === null ? "text-gray-800" : isPositive ? "text-green-600" : "text-red-600"
                }`}
              >
                {changePct === null ? "N/A" : `${isPositive ? "+" : ""}${changePct.toFixed(2)}%`}
              </p>
              <p className="text-xs text-gray-400 mt-1">Next trading day</p>
            </div>
            <div className="bg-white rounded-xl shadow-md p-5">
              <p className="text-xs text-gray-500">Signal</p>
              <span
                className={`inline-block mt-1 text-xs font-bold px-3 py-1.5 rounded ${
                  prediction.signal === "BUY"
                    ? "bg-green-100 text-green-700"
                    : prediction.signal === "SELL"
                    ? "bg-red-100 text-red-700"
                    : "bg-yellow-100 text-yellow-700"
                }`}
              >
                {prediction.signal}
              </span>
              <p className="text-xs text-gray-400 mt-1">
                {prediction.companyName || selectedCompany?.name || prediction.symbol}
              </p>
            </div>
          </div>

          <div className="bg-white rounded-xl shadow-md p-4 md:p-6">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
              <div>
                <h3 className="text-lg font-bold text-gray-800">Prediction Graph</h3>
                <p className="text-xs text-gray-500">
                  Recent close price with the predicted next-day price
                </p>
              </div>
              <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
                {algorithmLabel}
              </span>
            </div>
            <PredictionChart
              data={historyData}
              predictedPrice={predictedPrice}
            />
            {historyError && (
              <p className="mt-2 text-xs text-red-600">{historyError}</p>
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ModelBarChart models={prediction.models} />

            <div className="bg-white rounded-xl shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">Prediction Details</h3>
              <dl className="space-y-3">
                <div className="flex justify-between gap-4">
                  <dt className="text-sm text-gray-500">Company</dt>
                  <dd className="text-sm font-medium text-gray-800 text-right">
                    {prediction.companyName || selectedCompany?.name || "N/A"}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-sm text-gray-500">Stock Symbol</dt>
                  <dd className="text-sm font-mono font-medium text-blue-600 text-right">
                    {prediction.symbol}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-sm text-gray-500">Selected Algorithm</dt>
                  <dd className="text-sm font-medium text-gray-800 text-right">{algorithmLabel}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-sm text-gray-500">Current Price</dt>
                  <dd className="text-sm font-medium text-gray-800 text-right">
                    {formatMoney(currentPrice)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-sm text-gray-500">Predicted Price</dt>
                  <dd className="text-sm font-bold text-green-600 text-right">
                    {formatMoney(predictedPrice)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-sm text-gray-500">Ensemble Prediction</dt>
                  <dd className="text-sm font-medium text-gray-800 text-right">
                    {formatMoney(prediction.ensemblePrediction)}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-sm text-gray-500">Prediction Date</dt>
                  <dd className="text-sm font-medium text-gray-800 text-right">
                    {formatDate(prediction.createdAt)}
                  </dd>
                </div>
              </dl>

              {prediction.models && (
                <div className="mt-5 pt-4 border-t">
                  <p className="text-sm font-semibold text-gray-700 mb-2">Model Predictions</p>
                  <div className="space-y-2">
                    {Object.entries(prediction.models).map(([name, model]) => (
                      <div key={name} className="flex justify-between gap-4 text-sm">
                        <span className="text-gray-600">{MODEL_LABELS[name] || name}</span>
                        <span className="font-medium text-gray-800">
                          {formatMoney(model?.prediction)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default PredictionPage;
