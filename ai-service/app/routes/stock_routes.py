from fastapi import APIRouter, HTTPException
from app.services.data_service import data_service
from app.schemas.prediction_schema import StockDataResponse, StockInfoResponse

router = APIRouter(prefix="/api/stock-data", tags=["Stock Data"])


@router.get("/{symbol}", response_model=StockDataResponse)
def get_stock_data(symbol: str, period: str = "1y"):
    try:
        raw_df = data_service.fetch_stock_data(symbol, period)
        clean_df = data_service.clean_data(raw_df)
        data = clean_df.to_dict(orient="records")
        return StockDataResponse(symbol=symbol, data=data, rows=len(data))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{symbol}/info", response_model=StockInfoResponse)
def get_stock_info(symbol: str):
    try:
        info = data_service.get_stock_info(symbol)
        return StockInfoResponse(**info)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
