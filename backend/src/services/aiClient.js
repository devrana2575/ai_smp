const axios = require("axios");

const AI_SERVICE_URL =
  process.env.AI_SERVICE_URL || "http://localhost:8000";
const AI_SERVICE_TIMEOUT_MS = Number(
  process.env.AI_SERVICE_TIMEOUT_MS || 180000
);

const client = axios.create({
  baseURL: AI_SERVICE_URL,
  timeout: AI_SERVICE_TIMEOUT_MS,
  headers: { "Content-Type": "application/json" },
});

const structuredError = (error) => {
  const response = error.response;
  if (response?.data?.error) {
    return {
      status: response.status,
      error: response.data.error,
    };
  }
  if (response?.data?.detail?.error) {
    return {
      status: response.status,
      error: response.data.detail.error,
    };
  }
  if (response?.data?.detail) {
    return {
      status: response.status,
      error: {
        code: "ai_service_error",
        message:
          typeof response.data.detail === "string"
            ? response.data.detail
            : JSON.stringify(response.data.detail),
      },
    };
  }
  return {
    status: 502,
    error: {
      code: "ai_service_unavailable",
      message: error.message || "AI service request failed",
    },
  };
};

module.exports = {
  client,
  structuredError,
  AI_SERVICE_URL,
  AI_SERVICE_TIMEOUT_MS,
};
