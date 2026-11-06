const test = require("node:test");
const assert = require("node:assert/strict");

const { collectConfigProblems, parseOrigins } = require("../src/config/env");

const aiClientPath = require.resolve("../src/services/aiClient");

const loadAiClient = (env) => {
  const previous = process.env.AI_SERVICE_TOKEN;
  if (env === undefined) {
    delete process.env.AI_SERVICE_TOKEN;
  } else {
    process.env.AI_SERVICE_TOKEN = env;
  }
  delete require.cache[aiClientPath];
  const loaded = require(aiClientPath);
  if (previous === undefined) {
    delete process.env.AI_SERVICE_TOKEN;
  } else {
    process.env.AI_SERVICE_TOKEN = previous;
  }
  delete require.cache[aiClientPath];
  return loaded;
};

test("ai client forwards the internal service token when configured", () => {
  const { serviceHeaders } = loadAiClient("test-service-token");
  assert.equal(serviceHeaders["X-Internal-Service-Token"], "test-service-token");
});

test("ai client does not invent a service token when unset", () => {
  const { serviceHeaders } = loadAiClient(undefined);
  assert.equal(serviceHeaders["X-Internal-Service-Token"], undefined);
});

test("production config rejects weak secrets and wildcard CORS", () => {
  const problems = collectConfigProblems({
    NODE_ENV: "production",
    JWT_SECRET: "short",
    MONGODB_URI: "mongodb://db/ai-smp",
    AI_SERVICE_TOKEN: "short",
    CORS_ORIGINS: "*",
    AI_SERVICE_TIMEOUT_MS: "1000",
  });
  assert.ok(problems.some((item) => item.includes("JWT_SECRET")));
  assert.ok(problems.some((item) => item.includes("AI_SERVICE_TOKEN")));
  assert.ok(problems.some((item) => item.includes("wildcard CORS")));
});

test("rate-limit settings must be positive", () => {
  const problems = collectConfigProblems({
    NODE_ENV: "development",
    JWT_SECRET: "local-development-secret",
    MONGODB_URI: "mongodb://localhost:27017/ai-smp",
    CORS_ORIGINS: "http://localhost:5173",
    AI_SERVICE_TIMEOUT_MS: "180000",
    API_RATE_LIMIT_WINDOW_MS: "0",
    API_RATE_LIMIT_MAX: "0",
  });
  assert.ok(problems.some((item) => item.includes("API_RATE_LIMIT_WINDOW_MS")));
  assert.ok(problems.some((item) => item.includes("API_RATE_LIMIT_MAX")));
});

test("development config accepts explicit local origins", () => {
  const problems = collectConfigProblems({
    NODE_ENV: "development",
    JWT_SECRET: "local-development-secret",
    MONGODB_URI: "mongodb://localhost:27017/ai-smp",
    CORS_ORIGINS: "http://localhost:5173,http://localhost:3000",
    AI_SERVICE_TIMEOUT_MS: "180000",
  });
  assert.deepEqual(problems, []);
  assert.deepEqual(parseOrigins("http://a.test, http://b.test"), [
    "http://a.test",
    "http://b.test",
  ]);
});
