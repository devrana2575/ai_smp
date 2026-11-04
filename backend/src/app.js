require("dotenv").config();
const express = require("express");
const cors = require("cors");
const rateLimit = require("express-rate-limit");
const connectDB = require("./config/db");
const errorHandler = require("./middleware/error");

const authRoutes = require("./routes/auth.routes");
const companyRoutes = require("./routes/company.routes");
const predictionRoutes = require("./routes/prediction.routes");
const researchRoutes = require("./routes/research.routes");

const app = express();

connectDB();

app.use(cors({
  origin: ["http://localhost:5173", "http://localhost:3000"],
  credentials: true,
}));

app.use(express.json());

const limiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  message: { detail: "Too many requests, please try again later" },
});
app.use("/api/", limiter);

app.use("/api/auth", authRoutes);
app.use("/api/companies", companyRoutes);
app.use("/api/predictions", predictionRoutes);
app.use("/api/v2", researchRoutes);

app.get("/health", (req, res) => {
  res.json({ status: "healthy", service: "AI-SMP Backend" });
});

app.use(errorHandler);

module.exports = app;
