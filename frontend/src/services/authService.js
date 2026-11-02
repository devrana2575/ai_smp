import api from "./api";

export const authService = {
  register: async (name, email, password) => {
    const response = await api.post("/auth/register", { name, email, password });
    return response.data;
  },

  login: async (email, password) => {
    const response = await api.post("/auth/login", { email, password });
    return response.data;
  },

  getProfile: async () => {
    const response = await api.get("/auth/profile");
    return response.data;
  },

  updateProfile: async (data) => {
    const response = await api.put("/auth/profile", data);
    return response.data;
  },

  changePassword: async (currentPassword, newPassword) => {
    const response = await api.put("/auth/change-password", {
      currentPassword,
      newPassword,
    });
    return response.data;
  },
};
