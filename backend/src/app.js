require("dotenv").config();
const express = require("express");
const cors = require("cors");
const rateLimit = require("express-rate-limit");
const connectDB = require("./config/db");
const errorHandler = require("./middleware/error");
const {
  assertValidConfig,
  parseOrigins,
  requestId,
} = require("./config/env");

const authRoutes = require("./routes/auth.routes");
const companyRoutes = require("./routes/company.routes");
const predictionRoutes = require("./routes/prediction.routes");

if (process.env.NODE_ENV !== "test") {
  assertValidConfig();
}

const app = express();

connectDB();

app.use(
  cors({
    origin: parseOrigins(process.env.CORS_ORIGINS),
    credentials: true,
  })
);

app.use((req, res, next) => {
  req.id = req.headers["x-request-id"] || requestId();
  res.setHeader("X-Request-Id", req.id);
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "no-referrer");
  next();
});

app.use(express.json({ limit: "1mb" }));

const rateLimitWindowMs = Number(
  process.env.API_RATE_LIMIT_WINDOW_MS || 15 * 60 * 1000
);
const rateLimitMax = Number(
  process.env.API_RATE_LIMIT_MAX ||
    (process.env.NODE_ENV === "production" ? 600 : 3000)
);

const limiter = rateLimit({
  windowMs: rateLimitWindowMs,
  max: rateLimitMax,
  standardHeaders: true,
  legacyHeaders: false,
  skip: (req) => req.method === "OPTIONS",
  message: { detail: "Too many requests, please try again later" },
});
app.use("/api/", limiter);

app.use("/api/auth", authRoutes);
app.use("/api/companies", companyRoutes);
app.use("/api/predictions", predictionRoutes);

app.get("/health", (req, res) => {
  res.json({ status: "healthy", service: "AI-SMP Backend" });
});

app.use(errorHandler);

module.exports = app;
