from fastapi import APIRouter, HTTPException
from app.services.prediction_service import prediction_service
from app.schemas.prediction_schema import (
    TrainRequest,
    TrainResponse,
    PredictionResponse,
    ModelStatusResponse,
    EvaluationResponse,
    EvaluationSummaryResponse,
)

router = APIRouter(prefix="/api", tags=["Prediction"])


@router.post("/train/{symbol}", response_model=TrainResponse)
def train_models(symbol: str, request: TrainRequest = TrainRequest()):
    try:
        result = prediction_service.train_all_models(symbol, request.period)
        return TrainResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/predict/{symbol}", response_model=PredictionResponse)
def predict_stock(symbol: str):
    try:
        result = prediction_service.predict(symbol)
        return PredictionResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/model-status/{symbol}", response_model=ModelStatusResponse)
def get_model_status(symbol: str):
    try:
        status = prediction_service.get_model_status(symbol)
        return ModelStatusResponse(symbol=symbol, models=status)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/evaluate/{symbol}", response_model=EvaluationResponse)
def evaluate_models(symbol: str, request: TrainRequest = TrainRequest()):
    try:
        result = prediction_service.evaluate_saved_models(symbol, request.period)
        return EvaluationResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/evaluation-summary", response_model=EvaluationSummaryResponse)
def get_evaluation_summary():
    try:
        result = prediction_service.get_evaluation_summary()
        return EvaluationSummaryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/evaluation/{symbol}", response_model=EvaluationResponse)
def get_evaluation(symbol: str):
    try:
        result = prediction_service.get_evaluation(symbol)
        return EvaluationResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
