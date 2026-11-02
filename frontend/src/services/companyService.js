import api from "./api";

export const companyService = {
  getAll: async (category) => {
    const params = category ? `?category=${category}` : "";
    const response = await api.get(`/companies${params}`);
    return response.data;
  },

  getById: async (id) => {
    const response = await api.get(`/companies/${id}`);
    return response.data;
  },

  getBySymbol: async (symbol) => {
    const response = await api.get(`/companies/symbol/${symbol}`);
    return response.data;
  },

  create: async (data) => {
    const response = await api.post("/companies", data);
    return response.data;
  },

  update: async (id, data) => {
    const response = await api.put(`/companies/${id}`, data);
    return response.data;
  },

  delete: async (id) => {
    const response = await api.delete(`/companies/${id}`);
    return response.data;
  },

  seed: async () => {
    const response = await api.post("/companies/seed");
    return response.data;
  },
};
