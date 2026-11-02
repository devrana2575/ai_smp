import { Link } from "react-router-dom";

const RecentPredictions = ({ predictions = [] }) => {
  return (
    <div className="bg-white rounded-xl shadow-md p-6">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-bold text-gray-800">Recent Predictions</h3>
        <Link to="/results" className="text-sm text-blue-600 hover:underline">View All</Link>
      </div>
      {predictions.length > 0 ? (
        <div className="space-y-3">
          {predictions.slice(0, 8).map((pred) => (
            <div key={pred._id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${
                  pred.signal === "BUY" ? "bg-green-500" : pred.signal === "SELL" ? "bg-red-500" : "bg-yellow-500"
                }`}></div>
                <div>
                  <Link to={`/stock/${pred.symbol}`} className="font-semibold text-gray-800 hover:text-blue-600">
                    {pred.symbol}
                  </Link>
                  <p className="text-xs text-gray-500">{pred.companyName}</p>
                </div>
              </div>
              <div className="text-right">
                <span className={`text-xs font-bold px-2 py-1 rounded ${
                  pred.signal === "BUY" ? "bg-green-100 text-green-700" :
                  pred.signal === "SELL" ? "bg-red-100 text-red-700" :
                  "bg-yellow-100 text-yellow-700"
                }`}>
                  {pred.signal}
                </span>
                <p className="text-sm font-medium text-gray-700 mt-1">₹{pred.predictedPrice}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-gray-500 text-center py-8">No predictions yet</p>
      )}
    </div>
  );
};

export default RecentPredictions;
