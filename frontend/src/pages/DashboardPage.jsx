import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import StatsCard from "../components/dashboard/StatsCard";
import RecentPredictions from "../components/dashboard/RecentPredictions";
import { predictionService } from "../services/predictionService";
import Loading from "../components/common/Loading";
import toast from "react-hot-toast";

const ALGORITHM_LABELS = {
  linear_regression: "Linear Regression",
  decision_tree: "Decision Tree",
  random_forest: "Random Forest",
  svr: "Support Vector Regressor (SVR)",
  xgboost: "XGBoost",
};

const getAlgorithmLabel = (model) => {
  const name = model?.name || model?._id;
  if (!name) return "Not Evaluated";
  return ALGORITHM_LABELS[name] || name.replace(/_/g, " ").toUpperCase();
};

const DashboardPage = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const data = await predictionService.getDashboard();
      setStats(data);
    } catch {
      toast.error("Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <Loading message="Loading dashboard..." />;

  const bestModel = stats?.bestModel;
  const bestR2 = Number(bestModel?.avgR2);
  const hasEvaluation = Boolean(
    stats?.evaluation?.hasEvaluation &&
      bestModel &&
      Number.isFinite(bestR2)
  );
  const bestAlgorithm = hasEvaluation
    ? getAlgorithmLabel(bestModel)
    : "Not Evaluated";
  const accuracy = hasEvaluation
    ? `${(bestR2 * 100).toFixed(1)}%`
    : "Not Evaluated";
  const evaluatedCompanies = Number(
    bestModel?.evaluatedCompanies ?? stats?.evaluation?.evaluatedCompanies ?? 0
  );
  const accuracySubtitle = hasEvaluation
    ? `Test R² • ${evaluatedCompanies} ${
        evaluatedCompanies === 1 ? "company" : "companies"
      }`
    : "Train models to evaluate";

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatsCard
          title="Total Companies"
          value={stats?.totalCompanies || 0}
          color="blue"
          subtitle="Metal & Mining"
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          }
        />
        <StatsCard
          title="Predictions Made"
          value={stats?.totalPredictions || 0}
          color="green"
          subtitle="All time"
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          }
        />
        <StatsCard
          title="Best Algorithm"
          value={bestAlgorithm}
          color="purple"
          subtitle={
            hasEvaluation
              ? `Held-out test R²: ${(bestR2 * 100).toFixed(1)}%`
              : "No evaluation data"
          }
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
            </svg>
          }
        />
        <StatsCard
          title="Accuracy"
          value={accuracy}
          color="cyan"
          subtitle={accuracySubtitle}
          icon={
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-3">
          <RecentPredictions predictions={stats?.recentPredictions} />
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-md p-5 md:p-6">
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h3 className="text-lg font-bold text-gray-800">Research & model lifecycle</h3>
            <p className="text-sm text-gray-500">
              Walk-forward evaluation, return-target experiments, simulated backtests, versioned model activation, and prediction monitoring.
              These views report out-of-sample research results, not a promise of profitability.
            </p>
          </div>
          <Link to="/research/walk-forward" className="btn-primary text-sm whitespace-nowrap">
            Open research platform
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3 mt-5">
          {[
            ["/research/walk-forward", "Walk-forward", "Chronological folds and locked holdout"],
            ["/research/return-forecasting", "Return targets", "Absolute vs simple vs log return"],
            ["/research/backtesting", "Backtesting", "Costs, slippage, and risk metrics"],
            ["/research/registry", "Model registry", "Approve, activate, and roll back"],
            ["/research/monitoring", "Monitoring", "Prediction outcomes and feature drift"],
          ].map(([to, title, description]) => (
            <Link
              key={to}
              to={to}
              className="rounded-lg border border-gray-200 p-4 hover:border-blue-300 hover:bg-blue-50 transition"
            >
              <p className="font-semibold text-gray-800 text-sm">{title}</p>
              <p className="text-xs text-gray-500 mt-1">{description}</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
