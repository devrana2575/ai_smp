from pydantic import BaseModel
from typing import Optional, Dict, Any


class TrainRequest(BaseModel):
    period: Optional[str] = "1y"


class TrainResponse(BaseModel):
    symbol: str
    models: Dict[str, Any]
    training_samples: int
    testing_samples: int
    feature_columns: list
    split_method: Optional[str] = None
    best_model: Optional[str] = None
    best_model_label: Optional[str] = None
    best_r2_score: Optional[float] = None


class PredictionResponse(BaseModel):
    symbol: str
    current_price: float
    predicted_price: Optional[float]
    signal: str
    models: Dict[str, Any]
    ensemble_prediction: Optional[float]


class ModelStatusResponse(BaseModel):
    symbol: str
    models: Dict[str, bool]


class EvaluationResponse(BaseModel):
    symbol: str
    evaluation: Optional[Dict[str, Any]]
    best_model: Optional[str]
    best_model_label: Optional[str] = None
    best_model_metrics: Optional[Dict[str, Any]] = None
    best_r2_score: Optional[float] = None
    r2_percentage: Optional[float] = None
    ensemble_r2: Optional[float] = None
    evaluated_at: Optional[str] = None
    period: Optional[str] = None
    training_samples: Optional[int] = None
    testing_samples: Optional[int] = None
    split_method: Optional[str] = None
    evaluation_source: Optional[str] = None
    has_evaluation: Optional[bool] = None
    message: Optional[str] = None


class EvaluationSummaryResponse(BaseModel):
    has_evaluation: bool
    best_model: Optional[Dict[str, Any]] = None
    algorithms: Dict[str, Any] = {}
    evaluated_symbols: list = []
    evaluated_companies: int = 0
    evaluated_at: Optional[str] = None
    evaluation_source: Optional[str] = None
    split_method: Optional[str] = None
    message: Optional[str] = None


class StockDataResponse(BaseModel):
    symbol: str
    data: list
    rows: int


class StockInfoResponse(BaseModel):
    symbol: str
    name: str
    sector: str
    industry: str
    currentPrice: float
    marketCap: float


class MarketRegimeMetrics(BaseModel):
    latest_close: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ma_gap_pct: Optional[float] = None
    return_20d_pct: Optional[float] = None
    return_60d_pct: Optional[float] = None
    distance_from_sma_200_pct: Optional[float] = None


class MarketRegimeResponse(BaseModel):
    symbol: str
    regime: str
    label: str
    reason: str
    as_of: Optional[str] = None
    data_points: int
    metrics: MarketRegimeMetrics
    method: str
    source: str
    disclaimer: str


class ErrorResponse(BaseModel):
    detail: str
