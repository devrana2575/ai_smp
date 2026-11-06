const crypto = require("crypto");
const dotenv = require("dotenv");

dotenv.config();

const PLACEHOLDER_SECRETS = new Set([
  "replace-with-a-long-random-secret",
  "changeme",
  "secret",
]);

const parseOrigins = (raw) =>
  (raw || "http://localhost:5173,http://localhost:3000")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);

/**
 * Validate environment configuration without echoing secret values.
 * Returns a list of human-readable setting problems.
 */
const collectConfigProblems = (env = process.env) => {
  const production = (env.NODE_ENV || "development") === "production";
  const problems = [];

  const jwtSecret = env.JWT_SECRET || "";
  if (!jwtSecret) {
    problems.push("JWT_SECRET is required");
  } else if (PLACEHOLDER_SECRETS.has(jwtSecret)) {
    problems.push("JWT_SECRET must not be a placeholder value");
  } else if (production && jwtSecret.length < 32) {
    problems.push("JWT_SECRET must be at least 32 characters in production");
  }

  if (!env.MONGODB_URI) {
    problems.push("MONGODB_URI is required");
  }

  const serviceToken = env.AI_SERVICE_TOKEN || "";
  if (production && !serviceToken) {
    problems.push("AI_SERVICE_TOKEN is required in production");
  } else if (production && serviceToken.length < 32) {
    problems.push("AI_SERVICE_TOKEN must be at least 32 characters in production");
  }

  const origins = parseOrigins(env.CORS_ORIGINS);
  if (origins.length === 0) {
    problems.push("CORS_ORIGINS must contain at least one origin");
  }
  if (production && origins.some((origin) => origin === "*")) {
    problems.push("wildcard CORS origins are not allowed in production");
  }
  if (origins.some((origin) => !/^https?:\/\//.test(origin))) {
    problems.push("CORS_ORIGINS entries must be absolute http(s) URLs");
  }

  const timeout = Number(env.AI_SERVICE_TIMEOUT_MS || 180000);
  if (!Number.isFinite(timeout) || timeout <= 0) {
    problems.push("AI_SERVICE_TIMEOUT_MS must be a positive number");
  }

  return problems;
};

const assertValidConfig = (env = process.env) => {
  const problems = collectConfigProblems(env);
  if (problems.length > 0) {
    throw new Error(`Invalid configuration: ${problems.join("; ")}`);
  }
};

const requestId = () =>
  typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : crypto.randomBytes(16).toString("hex");

module.exports = {
  assertValidConfig,
  collectConfigProblems,
  parseOrigins,
  requestId,
};
