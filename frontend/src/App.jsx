import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { AuthProvider, useAuth } from "./context/AuthContext";

import Layout from "./components/layout/Layout";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import DashboardPage from "./pages/DashboardPage";
import CompanyPage from "./pages/CompanyPage";
import StockDetailPage from "./pages/StockDetailPage";
import PredictionPage from "./pages/PredictionPage";
import ModelComparisonPage from "./pages/ModelComparisonPage";
import ComparisonPage from "./pages/ComparisonPage";
import ResultsPage from "./pages/ResultsPage";
import ReportsPage from "./pages/ReportsPage";
import WalkForwardPage from "./pages/WalkForwardPage";
import ReturnForecastingPage from "./pages/ReturnForecastingPage";
import BacktestingPage from "./pages/BacktestingPage";
import ModelRegistryPage from "./pages/ModelRegistryPage";
import MonitoringPage from "./pages/MonitoringPage";

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;
  if (!user) return <Navigate to="/login" />;
  return children;
};

const PublicRoute = ({ children }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>;
  if (user) return <Navigate to="/dashboard" />;
  return children;
};

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
      <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />

      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/companies" element={<CompanyPage />} />
        <Route path="/stock/:symbol" element={<StockDetailPage />} />
        <Route path="/predict" element={<PredictionPage />} />
        <Route path="/predict/:symbol" element={<PredictionPage />} />
        <Route path="/compare" element={<ComparisonPage />} />
        <Route path="/compare/:symbol" element={<ModelComparisonPage />} />
        <Route path="/results" element={<ResultsPage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/research" element={<Navigate to="/research/walk-forward" replace />} />
        <Route path="/research/walk-forward" element={<WalkForwardPage />} />
        <Route path="/research/return-forecasting" element={<ReturnForecastingPage />} />
        <Route path="/research/backtesting" element={<BacktestingPage />} />
        <Route path="/research/registry" element={<ModelRegistryPage />} />
        <Route path="/research/monitoring" element={<MonitoringPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="min-h-screen bg-gray-100">
          <AppRoutes />
          <Toaster position="top-right" />
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
