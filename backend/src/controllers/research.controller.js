const { client, structuredError } = require("../services/aiClient");
const Prediction = require("../models/Prediction");
const Company = require("../models/Company");

const SYMBOL_PATTERN = /^[A-Za-z0-9^][A-Za-z0-9.^=&-]{0,31}$/;

const validSymbol = (symbol) =>
  typeof symbol === "string" &&
  symbol.length > 0 &&
  !symbol.includes("..") &&
  SYMBOL_PATTERN.test(symbol);

const reject = (res, status, code, message) =>
  res.status(status).json({ error: { code, message } });

const proxy = (handler) => async (req, res) => {
  try {
    const response = await handler(req);
    return res.status(response.status).json(response.data);
  } catch (error) {
    const parsed = structuredError(error);
    return res.status(parsed.status).json({ error: parsed.error });
  }
};

const requireSymbol = (req, res) => {
  const { symbol } = req.params;
  if (!validSymbol(symbol)) {
    reject(res, 400, "invalid_symbol", "Invalid stock symbol");
    return null;
  }
  return symbol;
};

const symbolOrThrow = (symbol) => {
  if (!validSymbol(symbol)) {
    const error = new Error("Invalid stock symbol");
    error.response = {
      status: 400,
      data: {
        error: { code: "invalid_symbol", message: "Invalid stock symbol" },
      },
    };
    throw error;
  }
  return symbol;
};

exports.latestWalkForward = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.get(`/api/v2/evaluation/walk-forward/${symbol}`);
});

exports.runWalkForward = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  const body = req.body || {};
  return client.post(`/api/v2/evaluation/walk-forward/${symbol}`, {
    period: body.period,
    folds: body.folds,
    holdout_fraction: body.holdout_fraction,
    min_train_samples: body.min_train_samples,
    min_validation_samples: body.min_validation_samples,
    min_holdout_samples: body.min_holdout_samples,
    initial_train_fraction: body.initial_train_fraction,
  });
});

exports.latestReturnExperiment = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.get(`/api/v2/forecasting/return-experiment/${symbol}`);
});

exports.runReturnExperiment = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  const body = req.body || {};
  return client.post(`/api/v2/forecasting/return-experiment/${symbol}`, {
    period: body.period,
    folds: body.folds,
    holdout_fraction: body.holdout_fraction,
    min_train_samples: body.min_train_samples,
    min_validation_samples: body.min_validation_samples,
    min_holdout_samples: body.min_holdout_samples,
    initial_train_fraction: body.initial_train_fraction,
  });
});

exports.latestBacktest = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.get(`/api/v2/backtesting/${symbol}`);
});

exports.runBacktest = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  const body = req.body || {};
  return client.post(`/api/v2/backtesting/${symbol}`, {
    period: body.period,
    folds: body.folds,
    holdout_fraction: body.holdout_fraction,
    model: body.model,
    signal_source: body.signal_source,
    starting_capital: body.starting_capital,
    transaction_cost_bps: body.transaction_cost_bps,
    slippage_bps: body.slippage_bps,
    max_capital_allocation: body.max_capital_allocation,
    buy_threshold: body.buy_threshold,
    sell_threshold: body.sell_threshold,
  });
});

exports.listReports = proxy(async () => client.get("/api/v2/reports"));

exports.getJob = proxy(async (req) => {
  if (!/^[A-Za-z0-9-]{1,64}$/.test(req.params.jobId || "")) {
    return Promise.reject({
      response: {
        status: 400,
        data: { error: { code: "invalid_job_id", message: "Invalid job id" } },
      },
    });
  }
  return client.get(`/api/v2/jobs/${req.params.jobId}`);
});

exports.listJobs = proxy(async (req) =>
  client.get("/api/v2/jobs", {
    params: { limit: req.query.limit || 50 },
  })
);

exports.listModels = proxy(async () => client.get("/api/v2/models"));

exports.getSymbolModels = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.get(`/api/v2/models/${symbol}`);
});

exports.getActiveModel = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.get(`/api/v2/models/${symbol}/active`);
});

exports.trainCandidate = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  const body = req.body || {};
  return client.post(`/api/v2/models/${symbol}/train`, {
    period: body.period,
    notes: body.notes,
  });
});

exports.approveCandidate = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  const body = req.body || {};
  return client.post(
    `/api/v2/models/${symbol}/approve/${encodeURIComponent(
      req.params.version
    )}`,
    {
      // The route is explicitly an approval action; only an explicit false
      // should remove approval.
      approved: body.approved === undefined ? true : Boolean(body.approved),
      approved_by: req.user?.email || req.user?.id || "admin",
    }
  );
});

exports.activateCandidate = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  const body = req.body || {};
  return client.post(
    `/api/v2/models/${symbol}/activate/${encodeURIComponent(
      req.params.version
    )}`,
    {
      approved: Boolean(body.approved),
      approved_by: req.user?.email || req.user?.id || "admin",
    }
  );
});

exports.rollbackModel = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  const body = req.body || {};
  return client.post(`/api/v2/models/${symbol}/rollback`, {
    approved: Boolean(body.approved),
    approved_by: req.user?.email || req.user?.id || "admin",
  });
});

exports.deactivateModel = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.post(`/api/v2/models/${symbol}/deactivate`);
});

exports.predictRegistered = async (req, res) => {
  const symbol = requireSymbol(req, res);
  if (!symbol) return;
  try {
    const response = await client.post(
      `/api/v2/forecasting/predict/${symbol}`,
      { record: true }
    );
    const prediction = response.data;
    if (
      prediction.predicted_price === null ||
      prediction.predicted_price === undefined
    ) {
      return res.status(409).json({
        error: {
          code: "no_prediction",
          message: "The active model did not produce a prediction",
        },
      });
    }
    const company = await Company.findOne({ symbol: symbol.toUpperCase() });
    const sanitizedModels = {};
    for (const [name, value] of Object.entries(prediction.models || {})) {
      if (value && typeof value.prediction === "number") {
        sanitizedModels[name] = { prediction: value.prediction };
      }
    }
    const saved = await Prediction.create({
      symbol: symbol.toUpperCase(),
      companyName: company?.name || symbol,
      currentPrice: prediction.current_price,
      predictedPrice: prediction.predicted_price,
      signal: ["BUY", "SELL", "HOLD"].includes(prediction.signal)
        ? prediction.signal
        : "HOLD",
      algorithm: `registry:${prediction.model_version || "unknown"}`,
      models: sanitizedModels,
      ensemblePrediction: prediction.ensemble_prediction,
      predictedBy: req.user?._id,
    });
    return res.json({ ...prediction, savedPredictionId: saved._id });
  } catch (error) {
    const parsed = structuredError(error);
    return res.status(parsed.status).json({ error: parsed.error });
  }
};

exports.monitoringSummary = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.get(`/api/v2/monitoring/${symbol}`);
});

exports.monitoringDrift = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.get(`/api/v2/monitoring/${symbol}/drift`);
});

exports.monitoringPredictions = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  const page = Number(req.query.page || 1);
  const pageSize = Number(req.query.page_size || 20);
  if (!Number.isInteger(page) || page < 1) {
    return Promise.reject({
      response: {
        status: 400,
        data: {
          error: { code: "invalid_page", message: "page must be >= 1" },
        },
      },
    });
  }
  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 200) {
    return Promise.reject({
      response: {
        status: 400,
        data: {
          error: {
            code: "invalid_page_size",
            message: "page_size must be between 1 and 200",
          },
        },
      },
    });
  }
  return client.get(`/api/v2/monitoring/${symbol}/predictions`, {
    params: { page, page_size: pageSize },
  });
});

exports.updateActuals = proxy(async (req) => {
  const symbol = symbolOrThrow(req.params.symbol);
  return client.post(`/api/v2/monitoring/${symbol}/update-actuals`, {
    period: req.body?.period || "6mo",
  });
});

// Exported for focused validation tests without starting Express or MongoDB.
exports.validSymbol = validSymbol;
exports.structuredError = structuredError;
