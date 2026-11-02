import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { companyService } from "../services/companyService";
import StockDataPanel from "../components/stock/StockDataPanel";
import Loading from "../components/common/Loading";
import toast from "react-hot-toast";

const CompanyPage = () => {
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCompany, setSelectedCompany] = useState(null);

  useEffect(() => {
    loadCompanies();
  }, [filter]);

  const loadCompanies = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await companyService.getAll(filter);
      setCompanies(Array.isArray(data) ? data : []);
    } catch (err) {
      const message = err.response?.data?.detail || "Failed to load companies";
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSeed = async () => {
    try {
      await companyService.seed();
      toast.success("Default companies seeded!");
      loadCompanies();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to seed companies");
    }
  };

  const filteredCompanies = companies.filter(
    (c) =>
      c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.symbol.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
        <div>
          <h2 className="text-2xl font-bold text-gray-800">Company & Data</h2>
          <p className="text-sm text-gray-500">
            Select a Metal & Mining company to view its historical stock data
          </p>
        </div>
        <button onClick={handleSeed} className="btn-secondary text-sm self-start sm:self-auto">
          Seed Default Companies
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-md p-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <svg className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              placeholder="Search by name or symbol..."
              className="input-field pl-10"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <select
            className="input-field w-full md:w-48"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">All Categories</option>
            <option value="Metal">Metal</option>
            <option value="Mining">Mining</option>
          </select>
          <select
            className="input-field w-full md:w-64"
            value={selectedCompany?.symbol || ""}
            onChange={(e) => {
              const company = companies.find((c) => c.symbol === e.target.value);
              setSelectedCompany(company || null);
            }}
          >
            <option value="">-- Select a company --</option>
            {companies.map((company) => (
              <option key={company._id} value={company.symbol}>
                {company.name} ({company.symbol})
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <Loading message="Loading companies..." />
      ) : error ? (
        <div className="bg-white rounded-xl shadow-md p-12 text-center">
          <p className="text-red-600 font-medium">{error}</p>
          <button onClick={loadCompanies} className="mt-3 btn-primary">
            Retry
          </button>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredCompanies.map((company) => {
              const isSelected = selectedCompany?.symbol === company.symbol;
              return (
                <div
                  key={company._id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setSelectedCompany(company)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setSelectedCompany(company);
                    }
                  }}
                  className={`bg-white rounded-xl shadow-md hover:shadow-lg transition-all p-5 cursor-pointer border-2 focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    isSelected ? "border-blue-500 ring-2 ring-blue-100" : "border-transparent"
                  }`}
                >
                  <div className="flex justify-between items-start mb-3 gap-2">
                    <div className="min-w-0">
                      <h3 className="font-bold text-gray-800 truncate">{company.name}</h3>
                      <p className="text-sm text-blue-600 font-mono">{company.symbol}</p>
                    </div>
                    <span className={`shrink-0 px-2 py-1 rounded-full text-xs font-medium ${
                      company.category === "Metal" ? "bg-blue-100 text-blue-700" : "bg-orange-100 text-orange-700"
                    }`}>
                      {company.category}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mb-4">
                    {[company.subCategory, company.exchange].filter(Boolean).join(" | ")}
                  </p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-blue-600">
                      {isSelected ? "Selected — data shown below" : "Click to view stock data"}
                    </span>
                    {isSelected && (
                      <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {filteredCompanies.length === 0 && (
            <div className="bg-white rounded-xl shadow-md p-12 text-center">
              <p className="text-gray-500 text-lg">No companies found</p>
              <p className="text-sm text-gray-400 mt-2">Try seeding default companies or adjust your search</p>
            </div>
          )}
        </>
      )}

      {selectedCompany && (
        <div className="space-y-4 pt-2">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <h2 className="text-xl font-bold text-gray-800">Stock Details</h2>
              <p className="text-sm text-gray-500">
                Historical data for {selectedCompany.name} ({selectedCompany.symbol})
              </p>
            </div>
            <Link
              to={`/predict?symbol=${selectedCompany.symbol}`}
              className="bg-green-600 hover:bg-green-700 text-white text-center px-4 py-2 rounded-lg transition text-sm font-medium self-start sm:self-auto"
            >
              Predict Stock Price
            </Link>
          </div>
          <StockDataPanel
            symbol={selectedCompany.symbol}
            company={selectedCompany}
            onClear={() => setSelectedCompany(null)}
          />
        </div>
      )}

      {!selectedCompany && !loading && !error && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-800">
          Select a company card above to load its historical stock price graph and OHLCV data.
        </div>
      )}
    </div>
  );
};

export default CompanyPage;
