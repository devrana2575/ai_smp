const mongoose = require("mongoose");

const predictionSchema = new mongoose.Schema(
  {
    symbol: {
      type: String,
      required: true,
      uppercase: true,
    },
    companyName: {
      type: String,
    },
    currentPrice: {
      type: Number,
    },
    predictedPrice: {
      type: Number,
    },
    signal: {
      type: String,
      enum: ["BUY", "SELL", "HOLD"],
    },
    algorithm: {
      type: String,
      default: "ensemble",
    },
    models: {
      type: Map,
      of: {
        prediction: Number,
        mae: Number,
        mse: Number,
        rmse: Number,
        r2_score: Number,
        mape: Number,
      },
    },
    ensemblePrediction: {
      type: Number,
    },
    predictedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
    },
  },
  { timestamps: true }
);

predictionSchema.index({ symbol: 1, createdAt: -1 });

module.exports = mongoose.model("Prediction", predictionSchema);
