import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import StockDataPanel from "../components/stock/StockDataPanel";
import { predictionService } from "../services/predictionService";
import toast from "react-hot-toast";

const MODEL_LABELS = {
  linear_regression: "Linear Regression",
  decision_tree: "Decision Tree",
  random_forest: "Random Forest",
  svr: "Support Vector Regressor",
  xgboost: "XGBoost",
};

const StockDetailPage = () => {
  const { symbol } = useParams();
  const [modelStatus, setModelStatus] = useState(null);
  const [statusError, setStatusError] = useState(null);
  const [training, setTraining] = useState(false);

  useEffect(() => {
    loadModelStatus();
  }, [symbol]);

  const loadModelStatus = async () => {
    setStatusError(null);
    try {
      const status = await predictionService.getModelStatus(symbol);
      setModelStatus(status);
    } catch (error) {
      setModelStatus(null);
      setStatusError(error.response?.data?.detail || "Model status unavailable");
    }
  };

  const handleTrain = async () => {
    setTraining(true);
    try {
      await predictionService.train(symbol);
      toast.success("Models trained successfully!");
      await loadModelStatus();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Training failed");
    } finally {
      setTraining(false);
    }
  };

  const trainedCount = modelStatus
    ? Object.values(modelStatus.models || {}).filter(Boolean).length
    : 0;

  return (
    <div className="space-y-6">
      <StockDataPanel
        symbol={symbol}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={handleTrain}
              disabled={training}
              className="btn-primary text-sm disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {training ? "Training..." : `Train Models (${trainedCount}/5)`}
            </button>
            <Link
              to={`/predict/${symbol}`}
              className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition text-sm font-medium"
            >
              Predict
            </Link>
            <Link to={`/compare/${symbol}`} className="btn-secondary text-sm">
              Compare Models
            </Link>
            <Link
              to={`/research/walk-forward?symbol=${encodeURIComponent(symbol)}`}
              className="btn-secondary text-sm"
            >
              Walk-forward
            </Link>
            <Link
              to={`/research/backtesting?symbol=${encodeURIComponent(symbol)}`}
              className="btn-secondary text-sm"
            >
              Backtest
            </Link>
          </div>
        }
      />

      <div className="bg-white rounded-xl shadow-md p-4 md:p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-bold text-gray-800">Model Training Status</h3>
            <p className="text-xs text-gray-500">
              {statusError || "All five ML models are used by the ensemble predictor."}
            </p>
          </div>
          {!statusError && (
            <span className="text-sm font-semibold text-gray-600">{trainedCount}/5 trained</span>
          )}
        </div>
        {statusError ? (
          <div className="p-4 rounded-lg bg-yellow-50 text-yellow-800 text-sm">
            {statusError}. Start the AI service to check model status.
          </div>
        ) : modelStatus ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {Object.entries(modelStatus.models || {}).map(([name, trained]) => (
              <div
                key={name}
                className={`p-4 rounded-lg text-center ${trained ? "bg-green-100" : "bg-gray-100"}`}
              >
                <p className="font-medium text-sm text-gray-800">{MODEL_LABELS[name] || name}</p>
                <p className={`text-xs mt-1 ${trained ? "text-green-700" : "text-gray-500"}`}>
                  {trained ? "Trained" : "Not Trained"}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-gray-500">Checking model status...</p>
        )}
      </div>
    </div>
  );
};

export default StockDetailPage;
