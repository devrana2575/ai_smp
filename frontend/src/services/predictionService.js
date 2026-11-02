import api from "./api";

export const predictionService = {
  train: async (symbol, period = "1y") => {
    const response = await api.post(`/predictions/train/${symbol}`, { period });
    return response.data;
  },

  predict: async (symbol, algorithm = "ensemble") => {
    const response = await api.post(`/predictions/predict/${symbol}`, { algorithm });
    return response.data;
  },

  getModelStatus: async (symbol) => {
    const response = await api.get(`/predictions/model-status/${symbol}`);
    return response.data;
  },

  evaluate: async (symbol, period = "1y") => {
    const response = await api.post(`/predictions/evaluate/${symbol}`, { period });
    return response.data;
  },

  getEvaluation: async (symbol) => {
    const response = await api.get(`/predictions/evaluation/${symbol}`);
    return response.data;
  },

  getEvaluationSummary: async () => {
    const response = await api.get("/predictions/evaluation-summary");
    return response.data;
  },

  getStockData: async (symbol, period) => {
    const params = period ? `?period=${period}` : "";
    const response = await api.get(`/predictions/stock-data/${symbol}${params}`);
    return response.data;
  },

  getStockInfo: async (symbol) => {
    const response = await api.get(`/predictions/stock-info/${symbol}`);
    return response.data;
  },

  getHistory: async (symbol) => {
    const params = symbol ? `?symbol=${symbol}` : "";
    const response = await api.get(`/predictions/history${params}`);
    return response.data;
  },

  getComparison: async (symbol) => {
    const response = await api.get(`/predictions/compare/${symbol}`);
    return response.data;
  },

  getDashboard: async () => {
    const response = await api.get("/predictions/dashboard");
    return response.data;
  },
};
