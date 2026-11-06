import json
import os

import pytest

from app.config import settings
from app.models.linear_regression import LinearRegressionModel
from app.models.svr_model import SVRModel
from app.services.data_service import data_service
from app.services.feature_engineering import feature_engineering
from app.services.model_registry_service import (
    MODEL_NAMES,
    ModelRegistryError,
    ModelRegistryService,
)


class StaticDataService:
    def __init__(self, df):
        self.df = df.copy()

    def fetch_stock_data(self, symbol, period="1y"):
        return self.df.copy()

    def clean_data(self, df):
        return data_service.clean_data(df)


@pytest.fixture
def registry(stock_data_factory, tmp_path):
    factories = {name: LinearRegressionModel for name in MODEL_NAMES}
    factories["svr"] = SVRModel
    return ModelRegistryService(
        registry_dir=str(tmp_path / "registry"),
        data_service_override=StaticDataService(stock_data_factory(240)),
        model_factories=factories,
    )


@pytest.fixture
def evaluation_report(tmp_path, monkeypatch):
    report_dir = tmp_path / "evaluation_reports"
    report_dir.mkdir()
    report = {
        "schema_version": "1.0",
        "symbol": "TEST.NS",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "status": "completed",
        "config": {"random_state": 42, "period": "2y", "folds_requested": 3},
        "data": {
            "period": "2y",
            "source": "synthetic_test_data",
            "feature_columns": list(feature_engineering.get_feature_columns()),
            "data_fingerprint_sha256": "a" * 64,
        },
        "best_performing_model": {
            "selected_model": "linear_regression",
            "selection_metric": "rmse",
            "development_metrics": {"rmse": 1.25, "mae": 0.9},
            "final_holdout_metrics": {"rmse": 1.5, "mae": 1.0},
        },
        "baseline_comparison": {
            "development": {
                "linear_regression": {
                    "beats_baseline_on_rmse": False,
                    "rmse_delta": 0.2,
                }
            },
            "final_holdout": {},
        },
    }
    path = report_dir / "TEST_NS_walk_forward.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(settings, "EVALUATION_REPORT_DIR", str(report_dir))
    return path


def _attach_and_approve(registry, version):
    registry.attach_evaluation_evidence(
        "TEST.NS", version, actor="admin@test"
    )
    return registry.approve_version(
        "TEST.NS", version, approved_by="admin@test"
    )


def test_candidate_training_activation_and_rollback(
    registry, evaluation_report
):
    candidate = registry.train_candidate("TEST.NS", period="1y")
    assert candidate["version"] == "v1"
    assert candidate["status"] == "candidate"
    assert candidate["approved"] is False
    assert candidate["production_artifact_unchanged"] is True
    assert registry.get_symbol("TEST.NS")["active_version"] is None
    assert len(registry.list_versions("TEST.NS")) == 1

    artifact_dir = os.path.join(
        registry.registry_dir, candidate["artifact_dir"]
    )
    assert os.path.isdir(artifact_dir)
    assert os.path.exists(os.path.join(artifact_dir, "linear_regression.pkl"))
    assert os.path.exists(os.path.join(artifact_dir, "svr_scaler.pkl"))

    with pytest.raises(ModelRegistryError, match="explicit approval"):
        registry.activate_version("TEST.NS", "v1", approved=False)

    with pytest.raises(ModelRegistryError, match="explicitly approved"):
        registry.activate_version("TEST.NS", "v1", approved=True)

    approved = _attach_and_approve(registry, "v1")
    assert approved["approved"] is True
    assert approved["evaluation_evidence"]["report_id"] == (
        "TEST_NS_walk_forward.json"
    )
    assert approved["evaluation_report_sha256"]

    active = registry.activate_version(
        "TEST.NS", "v1", approved=True, approved_by="admin@test"
    )
    assert active["status"] == "active"
    assert active["approved"] is True
    assert registry.get_symbol("TEST.NS")["active_version"] == "v1"

    second = registry.train_candidate("TEST.NS", period="1y")
    assert second["version"] == "v2"
    # Training a new candidate must not change the active version or its
    # artifacts.
    assert registry.get_symbol("TEST.NS")["active_version"] == "v1"
    assert os.path.exists(os.path.join(artifact_dir, "linear_regression.pkl"))
    assert second["candidate_vs_active"] is not None

    _attach_and_approve(registry, "v2")
    registry.activate_version(
        "TEST.NS", "v2", approved=True, approved_by="admin@test"
    )
    assert registry.get_symbol("TEST.NS")["active_version"] == "v2"
    rolled_back = registry.rollback("TEST.NS", actor="admin@test")
    assert rolled_back["version"] == "v1"
    assert registry.get_symbol("TEST.NS")["active_version"] == "v1"

    deactivated = registry.deactivate("TEST.NS", actor="admin@test")
    assert deactivated["active_version"] is None
    assert registry.get_symbol("TEST.NS")["active_version"] is None

    with open(registry.registry_path, encoding="utf-8") as handle:
        registry_json = json.load(handle)
    assert registry_json["schema_version"] == "1.0"
    assert registry_json["symbols"]["TEST.NS"]["versions"]["v1"]["status"] == "inactive"

    with open(registry.audit_path, encoding="utf-8") as handle:
        events = [json.loads(line) for line in handle if line.strip()]
    assert any(event["event"] == "version_activated" for event in events)
    assert any(event["event"] == "version_deactivated" for event in events)


def test_predict_with_active_and_missing_active(
    registry, evaluation_report
):
    with pytest.raises(ModelRegistryError, match="No active registered model"):
        registry.predict_with_active("TEST.NS")

    registry.train_candidate("TEST.NS")
    _attach_and_approve(registry, "v1")
    registry.activate_version(
        "TEST.NS", "v1", approved=True, approved_by="admin@test"
    )
    prediction = registry.predict_with_active("TEST.NS")
    assert prediction["model_version"] == "v1"
    assert prediction["current_price"] > 0
    assert prediction["predicted_price"] is not None
    assert prediction["signal"] in {"BUY", "SELL", "HOLD", "N/A"}
    assert set(prediction["models"]) == set(MODEL_NAMES)


def test_registry_requires_all_artifacts_for_activation(
    registry, evaluation_report
):
    candidate = registry.train_candidate("TEST.NS")
    _attach_and_approve(registry, "v1")
    artifact_dir = os.path.join(
        registry.registry_dir, candidate["artifact_dir"]
    )
    os.remove(os.path.join(artifact_dir, "random_forest.pkl"))

    with pytest.raises(ModelRegistryError, match="does not exist"):
        registry.activate_version(
            "TEST.NS", "v1", approved=True, approved_by="admin@test"
        )


def test_approval_requires_attached_evaluation_evidence(registry):
    registry.train_candidate("TEST.NS")
    with pytest.raises(ModelRegistryError, match="evaluation evidence"):
        registry.approve_version("TEST.NS", "v1", approved_by="admin@test")


def test_evidence_feature_schema_must_match_candidate(
    registry, evaluation_report
):
    registry.train_candidate("TEST.NS")
    report = json.loads(evaluation_report.read_text(encoding="utf-8"))
    report["data"]["feature_columns"] = report["data"]["feature_columns"][:-1]
    evaluation_report.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ModelRegistryError, match="feature schema"):
        registry.attach_evaluation_evidence("TEST.NS", "v1")


def test_registry_cannot_live_inside_saved_models(tmp_path):
    with pytest.raises(ValueError, match="must not be inside saved_models"):
        ModelRegistryService(registry_dir=settings.SAVED_MODELS_DIR)


def test_artifact_manifest_rejects_unexpected_entries(
    registry, evaluation_report
):
    registry.train_candidate("TEST.NS")
    with open(registry.registry_path, encoding="utf-8") as handle:
        registry_json = json.load(handle)
    entry = registry_json["symbols"]["TEST.NS"]["versions"]["v1"]
    entry["artifacts"]["unexpected.pkl"] = "unexpected.pkl"
    registry._save_registry(registry_json)
    _attach_and_approve(registry, "v1")
    with pytest.raises(ModelRegistryError, match="unexpected entries"):
        registry.activate_version(
            "TEST.NS", "v1", approved=True, approved_by="admin@test"
        )


def test_registry_summary(registry):
    registry.train_candidate("TEST.NS")
    summary = registry.summary()
    assert summary["total_symbols"] == 1
    assert summary["total_versions"] == 1
    assert summary["symbols"][0]["candidate_count"] == 1
    assert summary["symbols"][0]["active_version"] is None
