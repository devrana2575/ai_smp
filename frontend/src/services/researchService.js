import api from "./api";

const errorMessage = (error, fallback) =>
  error?.response?.data?.error?.message ||
  error?.response?.data?.detail ||
  error?.message ||
  fallback;

const researchService = {
  async latestWalkForward(symbol) {
    const response = await api.get(
      `/v2/evaluation/walk-forward/${encodeURIComponent(symbol)}`
    );
    return response.data;
  },

  async runWalkForward(symbol, options = {}) {
    const response = await api.post(
      `/v2/evaluation/walk-forward/${encodeURIComponent(symbol)}`,
      options
    );
    return response.data;
  },

  async latestReturnExperiment(symbol) {
    const response = await api.get(
      `/v2/forecasting/return-experiment/${encodeURIComponent(symbol)}`
    );
    return response.data;
  },

  async runReturnExperiment(symbol, options = {}) {
    const response = await api.post(
      `/v2/forecasting/return-experiment/${encodeURIComponent(symbol)}`,
      options
    );
    return response.data;
  },

  async latestBacktest(symbol) {
    const response = await api.get(
      `/v2/backtesting/${encodeURIComponent(symbol)}`
    );
    return response.data;
  },

  async runBacktest(symbol, options = {}) {
    const response = await api.post(
      `/v2/backtesting/${encodeURIComponent(symbol)}`,
      options
    );
    return response.data;
  },

  async getReports() {
    const response = await api.get("/v2/reports");
    return response.data;
  },

  async getJob(jobId) {
    const response = await api.get(`/v2/jobs/${encodeURIComponent(jobId)}`);
    return response.data;
  },

  async listJobs(limit = 20) {
    const response = await api.get("/v2/jobs", { params: { limit } });
    return response.data;
  },

  async listModels() {
    const response = await api.get("/v2/models");
    return response.data;
  },

  async getSymbolModels(symbol) {
    const response = await api.get(
      `/v2/models/${encodeURIComponent(symbol)}`
    );
    return response.data;
  },

  async getActiveModel(symbol) {
    const response = await api.get(
      `/v2/models/${encodeURIComponent(symbol)}/active`
    );
    return response.data;
  },

  async trainCandidate(symbol, options = {}) {
    const response = await api.post(
      `/v2/models/${encodeURIComponent(symbol)}/train`,
      options
    );
    return response.data;
  },

  async approveCandidate(symbol, version, approved = true) {
    const response = await api.post(
      `/v2/models/${encodeURIComponent(symbol)}/approve/${encodeURIComponent(
        version
      )}`,
      { approved }
    );
    return response.data;
  },

  async activateCandidate(symbol, version, approved = true) {
    const response = await api.post(
      `/v2/models/${encodeURIComponent(symbol)}/activate/${encodeURIComponent(
        version
      )}`,
      { approved }
    );
    return response.data;
  },

  async rollbackModel(symbol, approved = true) {
    const response = await api.post(
      `/v2/models/${encodeURIComponent(symbol)}/rollback`,
      { approved }
    );
    return response.data;
  },

  async deactivateModel(symbol) {
    const response = await api.post(
      `/v2/models/${encodeURIComponent(symbol)}/deactivate`
    );
    return response.data;
  },

  async predictRegistered(symbol) {
    const response = await api.post(
      `/v2/forecasting/predict/${encodeURIComponent(symbol)}`
    );
    return response.data;
  },

  async monitoringSummary(symbol) {
    const response = await api.get(
      `/v2/monitoring/${encodeURIComponent(symbol)}`
    );
    return response.data;
  },

  async monitoringDrift(symbol) {
    const response = await api.get(
      `/v2/monitoring/${encodeURIComponent(symbol)}/drift`
    );
    return response.data;
  },

  async monitoringPredictions(symbol, page = 1, pageSize = 20) {
    const response = await api.get(
      `/v2/monitoring/${encodeURIComponent(symbol)}/predictions`,
      { params: { page, page_size: pageSize } }
    );
    return response.data;
  },

  async updateActuals(symbol, period = "6mo") {
    const response = await api.post(
      `/v2/monitoring/${encodeURIComponent(symbol)}/update-actuals`,
      { period }
    );
    return response.data;
  },

  async waitForJob(jobId, options = {}) {
    const intervalMs = options.intervalMs || 2000;
    const timeoutMs = options.timeoutMs || 30 * 60 * 1000;
    const started = Date.now();
    while (Date.now() - started < timeoutMs) {
      const job = await this.getJob(jobId);
      if (options.onUpdate) options.onUpdate(job);
      if (job.status === "completed") return job;
      if (job.status === "failed") {
        throw new Error(job.error || "Background job failed");
      }
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
    throw new Error("Timed out waiting for the background job");
  },

  errorMessage,
};

export { researchService, errorMessage };
