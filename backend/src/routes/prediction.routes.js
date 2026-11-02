const express = require("express");
const router = express.Router();
const predictionController = require("../controllers/prediction.controller");
const { auth } = require("../middleware/auth");

router.post("/train/:symbol", auth, predictionController.trainModels);
router.post("/predict/:symbol", auth, predictionController.predict);
router.get("/model-status/:symbol", auth, predictionController.getModelStatus);
router.post("/evaluate/:symbol", auth, predictionController.evaluateModels);
router.get("/evaluation-summary", auth, predictionController.getEvaluationSummary);
router.get("/evaluation/:symbol", auth, predictionController.getEvaluation);
router.get("/stock-data/:symbol", auth, predictionController.getStockData);
router.get("/stock-info/:symbol", auth, predictionController.getStockInfo);
router.get("/history", auth, predictionController.getPredictionHistory);
router.get("/compare/:symbol", auth, predictionController.getModelComparison);
router.get("/dashboard", auth, predictionController.getDashboardStats);

module.exports = router;
