import { Outlet, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";

const pageTitles = {
  "/dashboard": "Dashboard",
  "/companies": "Company & Data",
  "/predict": "Prediction",
  "/compare": "Algorithm Comparison",
  "/results": "Results",
  "/reports": "Reports",
};

const getPageTitle = (pathname) => {
  if (pageTitles[pathname]) return pageTitles[pathname];
  if (pathname.startsWith("/stock/")) return "Stock Details";
  if (pathname.startsWith("/predict/")) return "Prediction";
  if (pathname.startsWith("/compare/")) return "Model Comparison";
  return "AI-Based Stock Market Prediction";
};

const Layout = () => {
  const location = useLocation();
  const title = getPageTitle(location.pathname);

  return (
    <div className="flex min-h-screen bg-gray-100">
      <Sidebar />
      <div className="flex-1 min-w-0 lg:ml-64">
        <Header title={title} />
        <main className="p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
