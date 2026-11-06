const { client } = require("../services/aiClient");
const Prediction = require("../models/Prediction");
const Company = require("../models/Company");

const VALID_ALGORITHMS = [
  "linear_regression",
  "decision_tree",
  "random_forest",
  "svr",
  "xgboost",
];

const calculateSignal = (currentPrice, predictedPrice) => {
  if (!currentPrice || predictedPrice === null || predictedPrice === undefined) {
    return "HOLD";
  }
  const diffPct = ((predictedPrice - currentPrice) / currentPrice) * 100;
  if (diffPct > 1) return "BUY";
  if (diffPct < -1) return "SELL";
  return "HOLD";
};

exports.trainModels = async (req, res) => {
  try {
    const { symbol } = req.params;
    const { period } = req.body || { period: "1y" };

    const response = await client.post(
      `/api/train/${encodeURIComponent(symbol)}`,
      { period }
    );

    res.json(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: `Training failed: ${message}` });
  }
};

exports.predict = async (req, res) => {
  try {
    const { symbol } = req.params;
    const requestedAlgorithm = req.body?.algorithm || "ensemble";
    const algorithm =
      requestedAlgorithm === "ensemble" || VALID_ALGORITHMS.includes(requestedAlgorithm)
        ? requestedAlgorithm
        : "ensemble";

    const response = await client.post(
      `/api/predict/${encodeURIComponent(symbol)}`
    );
    const predictionData = response.data;

    let predictedPrice = predictionData.predicted_price;
    let signal = predictionData.signal;

    if (predictedPrice === null || predictedPrice === undefined) {
      return res.status(400).json({
        detail: "No trained models found for this company. Please train the models first.",
      });
    }

    if (algorithm !== "ensemble") {
      const modelPrediction = predictionData.models?.[algorithm]?.prediction;
      if (modelPrediction === null || modelPrediction === undefined) {
        return res.status(400).json({
          detail: `${algorithm.replace("_", " ")} model is not trained. Please train the models first.`,
        });
      }
      predictedPrice = modelPrediction;
      signal = calculateSignal(predictionData.current_price, modelPrediction);
    }

    const company = await Company.findOne({ symbol: symbol.toUpperCase() });

    const savedPrediction = await Prediction.create({
      symbol: symbol.toUpperCase(),
      companyName: company?.name || symbol,
      currentPrice: predictionData.current_price,
      predictedPrice,
      signal,
      algorithm,
      models: predictionData.models,
      ensemblePrediction: predictionData.ensemble_prediction,
      predictedBy: req.user._id,
    });

    res.json(savedPrediction);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: `Prediction failed: ${message}` });
  }
};

exports.getModelStatus = async (req, res) => {
  try {
    const { symbol } = req.params;
    const response = await client.get(
      `/api/model-status/${encodeURIComponent(symbol)}`
    );
    res.json(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: message });
  }
};

exports.getEvaluation = async (req, res) => {
  try {
    const { symbol } = req.params;
    const response = await client.get(
      `/api/evaluation/${encodeURIComponent(symbol)}`
    );
    res.json(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: message });
  }
};

exports.evaluateModels = async (req, res) => {
  try {
    const { symbol } = req.params;
    const { period } = req.body || { period: "1y" };
    const response = await client.post(
      `/api/evaluate/${encodeURIComponent(symbol)}`,
      { period }
    );
    res.json(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: `Evaluation failed: ${message}` });
  }
};

exports.getEvaluationSummary = async (req, res) => {
  try {
    const response = await client.get("/api/evaluation-summary", {
      timeout: 10000,
    });
    res.json(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: message });
  }
};

exports.getStockData = async (req, res) => {
  try {
    const { symbol } = req.params;
    const { period } = req.query;
    const response = await client.get(
      `/api/stock-data/${encodeURIComponent(symbol)}`,
      { params: period ? { period } : {} }
    );
    res.json(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: message });
  }
};

exports.getStockInfo = async (req, res) => {
  try {
    const { symbol } = req.params;
    const response = await client.get(
      `/api/stock-data/${encodeURIComponent(symbol)}/info`
    );
    res.json(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: message });
  }
};

exports.getMarketRegime = async (req, res) => {
  try {
    const { symbol } = req.params;
    const response = await client.get(
      `/api/stock-data/${encodeURIComponent(symbol)}/regime`
    );
    res.json(response.data);
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: message });
  }
};

exports.getPredictionHistory = async (req, res) => {
  try {
    const { symbol } = req.query;
    const filter = {};
    if (symbol) filter.symbol = symbol.toUpperCase();

    const predictions = await Prediction.find(filter)
      .sort({ createdAt: -1 })
      .limit(50)
      .populate("predictedBy", "name email");

    res.json(predictions);
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};

exports.getModelComparison = async (req, res) => {
  try {
    const { symbol } = req.params;

    const evaluationResponse = await client.get(
      `/api/evaluation/${encodeURIComponent(symbol)}`
    );
    const historyResponse = await client.get(
      `/api/stock-data/${encodeURIComponent(symbol)}`,
      { params: { period: "1y" } }
    );

    res.json({
      evaluation: evaluationResponse.data,
      dataPoints: historyResponse.data.rows,
    });
  } catch (error) {
    const message = error.response?.data?.detail || error.message;
    res.status(500).json({ detail: message });
  }
};

exports.getDashboardStats = async (req, res) => {
  try {
    const totalCompanies = await Company.countDocuments({ isActive: true });
    const metalCompanies = await Company.countDocuments({ isActive: true, category: "Metal" });
    const miningCompanies = await Company.countDocuments({ isActive: true, category: "Mining" });
    const totalPredictions = await Prediction.countDocuments();

    const recentPredictions = await Prediction.find()
      .sort({ createdAt: -1 })
      .limit(10)
      .populate("predictedBy", "name");

    let bestModel = null;
    let evaluation = {
      hasEvaluation: false,
      evaluatedCompanies: 0,
      evaluatedAt: null,
      evaluationSource: null,
    };

    try {
      const evaluationResponse = await client.get("/api/evaluation-summary", {
        timeout: 10000,
      });
      const summary = evaluationResponse.data;

      if (summary?.has_evaluation && summary?.best_model) {
        const model = summary.best_model;
        const averageR2 = Number(model.average_r2 ?? model.avgR2 ?? model.r2_score);

        if (Number.isFinite(averageR2)) {
          bestModel = {
            _id: model.algorithm || model.name,
            name: model.algorithm || model.name,
            label: model.label,
            avgR2: averageR2,
            r2Percentage: Number(
              model.r2_percentage ?? (averageR2 * 100).toFixed(2)
            ),
            metrics: model.metrics || null,
            evaluatedCompanies: model.evaluated_companies || 0,
            evaluatedAt: summary.evaluated_at || null,
          };
        }
      }

      evaluation = {
        hasEvaluation: Boolean(summary?.has_evaluation && bestModel),
        evaluatedCompanies: summary?.evaluated_companies || 0,
        evaluatedAt: summary?.evaluated_at || null,
        evaluationSource: summary?.evaluation_source || null,
        algorithms: summary?.algorithms || null,
      };
    } catch (evaluationError) {
      console.log("Evaluation summary error:", evaluationError.message);
    }

    res.json({
      totalCompanies,
      metalCompanies,
      miningCompanies,
      totalPredictions,
      recentPredictions,
      bestModel,
      evaluation,
    });
  } catch (error) {
    res.status(500).json({ detail: error.message });
  }
};
