const express = require("express");
const rateLimit = require("express-rate-limit");
const router = express.Router();
const controller = require("../controllers/research.controller");
const { auth, adminOnly } = require("../middleware/auth");

const expensiveLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 8,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: {
      code: "rate_limited",
      message: "Too many expensive research requests; please wait and retry",
    },
  },
});

const readLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 240,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: {
      code: "rate_limited",
      message: "Too many research requests; please wait and retry",
    },
  },
});

router.use(auth);
router.use(readLimiter);

// Evaluation and research experiments
router.get(
  "/evaluation/walk-forward/:symbol",
  controller.latestWalkForward
);
router.post(
  "/evaluation/walk-forward/:symbol",
  expensiveLimiter,
  adminOnly,
  controller.runWalkForward
);
router.get(
  "/forecasting/return-experiment/:symbol",
  controller.latestReturnExperiment
);
router.post(
  "/forecasting/return-experiment/:symbol",
  expensiveLimiter,
  adminOnly,
  controller.runReturnExperiment
);

// Backtesting
router.get("/backtesting/:symbol", controller.latestBacktest);
router.post(
  "/backtesting/:symbol",
  expensiveLimiter,
  adminOnly,
  controller.runBacktest
);

// Reports and jobs
router.get("/reports", controller.listReports);
router.get("/jobs", controller.listJobs);
router.get("/jobs/:jobId", controller.getJob);

// Model registry and lifecycle
router.get("/models", controller.listModels);
router.get("/models/:symbol", controller.getSymbolModels);
router.get("/models/:symbol/active", controller.getActiveModel);
router.post(
  "/models/:symbol/train",
  expensiveLimiter,
  adminOnly,
  controller.trainCandidate
);
router.post(
  "/models/:symbol/approve/:version",
  adminOnly,
  controller.approveCandidate
);
router.post(
  "/models/:symbol/activate/:version",
  adminOnly,
  controller.activateCandidate
);
router.post(
  "/models/:symbol/rollback",
  adminOnly,
  controller.rollbackModel
);
router.post(
  "/models/:symbol/deactivate",
  adminOnly,
  controller.deactivateModel
);

// Registered-model prediction (does not change the legacy prediction path)
router.post(
  "/forecasting/predict/:symbol",
  expensiveLimiter,
  controller.predictRegistered
);

// Monitoring
router.get("/monitoring/:symbol", controller.monitoringSummary);
router.get("/monitoring/:symbol/drift", controller.monitoringDrift);
router.get(
  "/monitoring/:symbol/predictions",
  controller.monitoringPredictions
);
router.post(
  "/monitoring/:symbol/update-actuals",
  expensiveLimiter,
  adminOnly,
  controller.updateActuals
);

module.exports = router;
