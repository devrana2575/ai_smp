"""Additive research and model-lifecycle API (v2).

These routes are mounted under ``/api/v2``. They do not alter the existing
legacy prediction/evaluation endpoints. Authentication and authorization are
enforced by the Express gateway; the FastAPI service is intended to be
internal-only.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.schemas.research_schema import (
    ActivationRequest,
    ApprovalRequest,
    BacktestRequest,
    CandidateTrainRequest,
    EvaluationRunRequest,
    EvidenceRequest,
    PredictionRequest,
    ReturnExperimentRequest,
    UpdateActualsRequest,
)
from app.services.backtesting_service import (
    BacktestConfig,
    SensitivityConfig,
    backtesting_service,
)
from app.services.data_service import validate_symbol
from app.services.job_service import job_service
from app.services.model_monitoring_service import model_monitoring_service
from app.services.model_registry_service import (
    ModelRegistryError,
    model_registry_service,
)
from app.services.return_forecasting_service import return_forecasting_service
from app.services.walk_forward_evaluation import (
    EvaluationConfig,
    walk_forward_evaluation_service,
)


router = APIRouter(prefix="/api/v2", tags=["Research v2"])


def _error(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            }
        },
    )


def _evaluation_config(payload: EvaluationRunRequest) -> EvaluationConfig:
    base = walk_forward_evaluation_service.config
    return EvaluationConfig(
        period=payload.period or base.period,
        folds=payload.folds if payload.folds is not None else base.folds,
        holdout_fraction=(
            payload.holdout_fraction
            if payload.holdout_fraction is not None
            else base.holdout_fraction
        ),
        min_train_samples=(
            payload.min_train_samples
            if payload.min_train_samples is not None
            else base.min_train_samples
        ),
        min_validation_samples=(
            payload.min_validation_samples
            if payload.min_validation_samples is not None
            else base.min_validation_samples
        ),
        min_holdout_samples=(
            payload.min_holdout_samples
            if payload.min_holdout_samples is not None
            else base.min_holdout_samples
        ),
        initial_train_fraction=(
            payload.initial_train_fraction
            if payload.initial_train_fraction is not None
            else base.initial_train_fraction
        ),
        selection_metric=base.selection_metric,
        random_state=base.random_state,
    )


def _sensitivity_config(request: BacktestRequest) -> SensitivityConfig:
    defaults = SensitivityConfig()
    thresholds = defaults.threshold_scenarios
    if request.threshold_scenarios is not None:
        thresholds = tuple(
            tuple(float(value) for value in pair)
            for pair in request.threshold_scenarios
        )
    return SensitivityConfig(
        enabled=request.run_sensitivity,
        cost_scenarios_bps=(
            tuple(float(value) for value in request.cost_scenarios_bps)
            if request.cost_scenarios_bps is not None
            else defaults.cost_scenarios_bps
        ),
        slippage_scenarios_bps=(
            tuple(float(value) for value in request.slippage_scenarios_bps)
            if request.slippage_scenarios_bps is not None
            else defaults.slippage_scenarios_bps
        ),
        threshold_scenarios=thresholds,
    )


def _report_path(directory: str, symbol: str, suffix: str) -> str:
    normalized = validate_symbol(symbol)
    return os.path.join(
        directory, normalized.replace(".", "_") + suffix
    )


def _read_json(path: str, code: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise _error(
            404,
            code,
            "Report has not been generated for this symbol",
            {"path": os.path.basename(path)},
        )
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        # Never return filesystem paths or parser details to clients.
        raise _error(
            500, "report_read_failed", "Could not read the stored report"
        )
    if not isinstance(payload, dict):
        raise _error(500, "invalid_report", "Stored report is not an object")
    return payload


def _run_walk_forward(symbol: str, config: EvaluationConfig) -> Dict[str, Any]:
    return walk_forward_evaluation_service.evaluate_symbol(
        symbol, config=config, write_report=True
    )


def _run_return_experiment(
    symbol: str, config: EvaluationConfig
) -> Dict[str, Any]:
    return return_forecasting_service.evaluate_symbol(
        symbol, config=config, write_report=True
    )


def _run_backtest(symbol: str, request: BacktestRequest) -> Dict[str, Any]:
    evaluation_config = _evaluation_config(request)
    evaluation_report = walk_forward_evaluation_service.evaluate_symbol(
        symbol, config=evaluation_config, write_report=False
    )
    base = backtesting_service.config
    config = BacktestConfig(
        starting_capital=(
            request.starting_capital
            if request.starting_capital is not None
            else base.starting_capital
        ),
        transaction_cost_bps=(
            request.transaction_cost_bps
            if request.transaction_cost_bps is not None
            else base.transaction_cost_bps
        ),
        slippage_bps=(
            request.slippage_bps
            if request.slippage_bps is not None
            else base.slippage_bps
        ),
        max_capital_allocation=(
            request.max_capital_allocation
            if request.max_capital_allocation is not None
            else base.max_capital_allocation
        ),
        buy_threshold=(
            request.buy_threshold
            if request.buy_threshold is not None
            else base.buy_threshold
        ),
        sell_threshold=(
            request.sell_threshold
            if request.sell_threshold is not None
            else base.sell_threshold
        ),
        risk_free_rate=base.risk_free_rate,
        periods_per_year=base.periods_per_year,
        model_name=request.model,
        signal_source=request.signal_source,
        liquidate_at_end=base.liquidate_at_end,
    )
    config.validate()
    sensitivity = _sensitivity_config(request)
    sensitivity.validate()
    return backtesting_service.run_symbol(
        symbol,
        config=config,
        evaluation_report=evaluation_report,
        write_report=True,
        sensitivity=sensitivity,
    )


# ----------------------------------------------------------------------
# Walk-forward / return experiments / backtests
# ----------------------------------------------------------------------
@router.get("/evaluation/walk-forward/{symbol}")
def latest_walk_forward(symbol: str):
    try:
        path = _report_path(
            settings.EVALUATION_REPORT_DIR,
            symbol,
            "_walk_forward.json",
        )
        return _read_json(path, "walk_forward_report_not_found")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_symbol", str(exc))


@router.post("/evaluation/walk-forward/{symbol}", status_code=202)
def run_walk_forward(symbol: str, request: EvaluationRunRequest):
    try:
        normalized = validate_symbol(symbol)
        config = _evaluation_config(request)
        config.validate()
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_request", str(exc))
    job = job_service.submit(
        "walk_forward_evaluation",
        _run_walk_forward,
        normalized,
        config,
    )
    return {"job": job}


@router.get("/forecasting/return-experiment/{symbol}")
def latest_return_experiment(symbol: str):
    try:
        path = _report_path(
            settings.RETURN_REPORT_DIR,
            symbol,
            "_return_forecasting.json",
        )
        return _read_json(path, "return_report_not_found")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_symbol", str(exc))


@router.post("/forecasting/return-experiment/{symbol}", status_code=202)
def run_return_experiment(symbol: str, request: ReturnExperimentRequest):
    try:
        normalized = validate_symbol(symbol)
        config = _evaluation_config(request)
        config.validate()
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_request", str(exc))
    job = job_service.submit(
        "return_forecasting_experiment",
        _run_return_experiment,
        normalized,
        config,
    )
    return {"job": job}


@router.get("/backtesting/{symbol}")
def latest_backtest(symbol: str):
    try:
        path = _report_path(
            settings.BACKTEST_REPORT_DIR, symbol, "_backtest.json"
        )
        return _read_json(path, "backtest_report_not_found")
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_symbol", str(exc))


@router.post("/backtesting/{symbol}", status_code=202)
def run_backtest(symbol: str, request: BacktestRequest):
    try:
        normalized = validate_symbol(symbol)
        config = _evaluation_config(request)
        config.validate()
        if (
            request.buy_threshold is not None
            and request.sell_threshold is not None
            and request.buy_threshold < request.sell_threshold
        ):
            raise ValueError("buy_threshold must be >= sell_threshold")
        _sensitivity_config(request).validate()
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_request", str(exc))
    job = job_service.submit(
        "backtest", _run_backtest, normalized, request
    )
    return {"job": job}


@router.get("/reports")
def list_reports():
    categories = {
        "walk_forward": settings.EVALUATION_REPORT_DIR,
        "return_forecasting": settings.RETURN_REPORT_DIR,
        "backtesting": settings.BACKTEST_REPORT_DIR,
        "jobs": settings.JOB_STATE_DIR,
    }
    output: Dict[str, Any] = {}
    for category, directory in categories.items():
        files = []
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory)):
                path = os.path.join(directory, name)
                if os.path.isfile(path):
                    files.append(
                        {
                            "name": name,
                            "size_bytes": os.path.getsize(path),
                            "modified_at": os.path.getmtime(path),
                        }
                    )
        output[category] = files
    return {"schema_version": "1.0", "categories": output}


# ----------------------------------------------------------------------
# Jobs
# ----------------------------------------------------------------------
@router.get("/jobs")
def list_jobs(limit: int = Query(default=50, ge=1, le=200)):
    return {"jobs": job_service.list_jobs(limit=limit)}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = job_service.get_job(job_id)
    if job is None:
        raise _error(404, "job_not_found", "Job does not exist")
    return job


# ----------------------------------------------------------------------
# Model registry / lifecycle
# ----------------------------------------------------------------------
@router.get("/models")
def list_models():
    return model_registry_service.summary()


@router.get("/models/{symbol}")
def get_symbol_models(symbol: str):
    try:
        normalized = validate_symbol(symbol)
        return {
            "symbol": normalized,
            "registry": model_registry_service.get_symbol(normalized),
            "versions": model_registry_service.list_versions(normalized),
        }
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_model_request", str(exc))


@router.get("/models/{symbol}/active")
def get_active_model(symbol: str):
    try:
        normalized = validate_symbol(symbol)
        active = model_registry_service.get_active(normalized)
        if active is None:
            raise _error(
                404,
                "no_active_model",
                f"No active registered model for {normalized}",
            )
        return active
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_model_request", str(exc))


@router.post("/models/{symbol}/train", status_code=202)
def train_candidate(symbol: str, request: CandidateTrainRequest):
    try:
        normalized = validate_symbol(symbol)
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_symbol", str(exc))
    job = job_service.submit(
        "candidate_training",
        model_registry_service.train_candidate,
        normalized,
        request.period,
        request.notes,
        "api",
    )
    return {"job": job}


@router.post("/models/{symbol}/evidence/{version}")
def attach_candidate_evidence(
    symbol: str, version: str, request: EvidenceRequest
):
    try:
        normalized = validate_symbol(symbol)
        return model_registry_service.attach_evaluation_evidence(
            normalized,
            version,
            report_id=request.report_id,
            actor="api",
        )
    except ModelRegistryError as exc:
        raise _error(400, "registry_error", str(exc))
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_model_request", str(exc))


@router.post("/models/{symbol}/approve/{version}")
def approve_candidate(
    symbol: str, version: str, request: ApprovalRequest
):
    try:
        normalized = validate_symbol(symbol)
        if request.approved:
            # Approval is evidence-based. Load and hash the completed
            # walk-forward report before recording the approval.
            model_registry_service.attach_evaluation_evidence(
                normalized,
                version,
                report_id=request.evaluation_report_id,
                actor=request.approved_by or "admin",
            )
        return model_registry_service.approve_version(
            normalized,
            version,
            approved_by=request.approved_by or "admin",
            approved=request.approved,
        )
    except ModelRegistryError as exc:
        raise _error(400, "registry_error", str(exc))
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_model_request", str(exc))


@router.post("/models/{symbol}/activate/{version}")
def activate_candidate(
    symbol: str, version: str, request: ActivationRequest
):
    try:
        normalized = validate_symbol(symbol)
        return model_registry_service.activate_version(
            normalized,
            version,
            approved=request.approved,
            approved_by=request.approved_by or "admin",
        )
    except ModelRegistryError as exc:
        raise _error(400, "registry_error", str(exc))
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_model_request", str(exc))


@router.post("/models/{symbol}/rollback")
def rollback_model(symbol: str, request: ApprovalRequest):
    try:
        normalized = validate_symbol(symbol)
        if not request.approved:
            raise ModelRegistryError(
                "Rollback requires explicit approval (approved=true)"
            )
        return model_registry_service.rollback(
            normalized, actor=request.approved_by or "admin"
        )
    except ModelRegistryError as exc:
        raise _error(400, "registry_error", str(exc))
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_model_request", str(exc))


@router.post("/models/{symbol}/deactivate")
def deactivate_model(symbol: str):
    try:
        normalized = validate_symbol(symbol)
        return model_registry_service.deactivate(normalized, actor="admin")
    except ModelRegistryError as exc:
        raise _error(400, "registry_error", str(exc))
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "invalid_model_request", str(exc))


@router.post("/forecasting/predict/{symbol}")
def predict_with_registered_model(
    symbol: str, request: Optional[PredictionRequest] = None
):
    try:
        request = request or PredictionRequest()
        normalized = validate_symbol(symbol)
        prediction = model_registry_service.predict_with_active(normalized)
        if request.record:
            prediction["prediction_id"] = model_monitoring_service.record_prediction(
                normalized,
                prediction,
                model_id=prediction.get("model_id"),
                model_version=prediction.get("model_version"),
            )["prediction_id"]
        return prediction
    except ModelRegistryError as exc:
        raise _error(409, "registry_unavailable", str(exc))
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "prediction_failed", str(exc))


# ----------------------------------------------------------------------
# Monitoring
# ----------------------------------------------------------------------
@router.get("/monitoring/{symbol}")
def monitoring_summary(symbol: str):
    try:
        return model_monitoring_service.monitoring_summary(symbol)
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "monitoring_failed", str(exc))


@router.get("/monitoring/{symbol}/drift")
def monitoring_drift(symbol: str):
    try:
        return model_monitoring_service.drift_report(symbol)
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "drift_failed", str(exc))


@router.get("/monitoring/{symbol}/predictions")
def monitoring_predictions(
    symbol: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    try:
        return model_monitoring_service.list_predictions(
            symbol, page=page, page_size=page_size
        )
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "monitoring_failed", str(exc))


@router.post("/monitoring/{symbol}/update-actuals")
def monitoring_update_actuals(symbol: str, request: UpdateActualsRequest):
    try:
        return model_monitoring_service.update_actuals(
            symbol, period=request.period
        )
    except Exception as exc:  # noqa: BLE001
        raise _error(400, "actuals_update_failed", str(exc))
