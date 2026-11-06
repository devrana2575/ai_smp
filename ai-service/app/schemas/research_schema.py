from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class EvaluationRunRequest(BaseModel):
    period: Optional[str] = Field(default=None, max_length=16)
    folds: Optional[int] = Field(default=None, ge=1, le=20)
    holdout_fraction: Optional[float] = Field(default=None, ge=0.05, le=0.5)
    min_train_samples: Optional[int] = Field(default=None, ge=20, le=5000)
    min_validation_samples: Optional[int] = Field(default=None, ge=5, le=1000)
    min_holdout_samples: Optional[int] = Field(default=None, ge=5, le=1000)
    initial_train_fraction: Optional[float] = Field(default=None, ge=0.2, le=0.9)


class ReturnExperimentRequest(EvaluationRunRequest):
    pass


class BacktestRequest(EvaluationRunRequest):
    model: Optional[str] = Field(default=None, max_length=64)
    signal_source: Literal["selected", "ensemble"] = "selected"
    starting_capital: Optional[float] = Field(default=None, gt=0, le=1e12)
    transaction_cost_bps: Optional[float] = Field(default=None, ge=0, le=5000)
    slippage_bps: Optional[float] = Field(default=None, ge=0, le=5000)
    max_capital_allocation: Optional[float] = Field(
        default=None, gt=0, le=1
    )
    buy_threshold: Optional[float] = Field(default=None, ge=-1, le=1)
    sell_threshold: Optional[float] = Field(default=None, ge=-1, le=1)
    run_sensitivity: bool = True
    cost_scenarios_bps: Optional[List[float]] = Field(
        default=None, max_length=20
    )
    slippage_scenarios_bps: Optional[List[float]] = Field(
        default=None, max_length=20
    )
    threshold_scenarios: Optional[List[List[float]]] = Field(
        default=None, max_length=20
    )


class CandidateTrainRequest(BaseModel):
    period: Optional[str] = Field(default=None, max_length=16)
    notes: Optional[str] = Field(default=None, max_length=2000)


class ApprovalRequest(BaseModel):
    approved: bool = False
    approved_by: Optional[str] = Field(default=None, max_length=256)
    evaluation_report_id: Optional[str] = Field(default=None, max_length=256)


class EvidenceRequest(BaseModel):
    report_id: Optional[str] = Field(default=None, max_length=256)


class ActivationRequest(ApprovalRequest):
    pass


class UpdateActualsRequest(BaseModel):
    period: str = Field(default="6mo", max_length=16)


class PredictionRequest(BaseModel):
    record: bool = True
