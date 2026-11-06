import json
import time

from fastapi.testclient import TestClient

from app.main import app
from app.routes import research_routes
from app.services.model_registry_service import ModelRegistryError


SERVICE_TOKEN = "test-internal-service-token-0123456789"
client = TestClient(
    app, headers={"X-Internal-Service-Token": SERVICE_TOKEN}
)


def _wait_for_job(job_id, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get(f"/api/v2/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError("Background job did not finish")


def test_latest_walk_forward_report_and_structured_404(tmp_path, monkeypatch):
    monkeypatch.setattr(
        research_routes.settings,
        "EVALUATION_REPORT_DIR",
        str(tmp_path),
    )
    (tmp_path / "TEST_NS_walk_forward.json").write_text(
        json.dumps({"symbol": "TEST.NS", "status": "completed"}),
        encoding="utf-8",
    )

    response = client.get("/api/v2/evaluation/walk-forward/TEST.NS")
    assert response.status_code == 200
    assert response.json()["symbol"] == "TEST.NS"

    missing = client.get("/api/v2/evaluation/walk-forward/OTHER.NS")
    assert missing.status_code == 404
    assert missing.json()["detail"]["error"]["code"] == "walk_forward_report_not_found"


def test_invalid_symbol_is_structured_400():
    response = client.get("/api/v2/evaluation/walk-forward/BAD_SYMBOL")
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "invalid_symbol"


def test_walk_forward_job_and_polling(monkeypatch):
    def fake_run(symbol, config):
        return {"symbol": symbol, "status": "completed", "config": config.to_dict()}

    monkeypatch.setattr(research_routes, "_run_walk_forward", fake_run)
    response = client.post(
        "/api/v2/evaluation/walk-forward/TEST.NS",
        json={"folds": 2, "holdout_fraction": 0.2},
    )
    assert response.status_code == 202
    job = response.json()["job"]
    completed = _wait_for_job(job["job_id"])
    assert completed["status"] == "completed"
    assert completed["result"]["symbol"] == "TEST.NS"
    assert completed["result"]["config"]["folds_requested"] == 2

    assert client.get("/api/v2/jobs/not-a-real-job").status_code == 404


def test_backtest_rejects_inverted_thresholds(monkeypatch):
    def fake_run(symbol, config):
        raise AssertionError("job should not be submitted")

    monkeypatch.setattr(research_routes, "_run_backtest", fake_run)
    response = client.post(
        "/api/v2/backtesting/TEST.NS",
        json={"buy_threshold": -0.1, "sell_threshold": 0.1},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "invalid_request"


def test_activation_requires_explicit_approval():
    response = client.post(
        "/api/v2/models/TEST.NS/activate/v1",
        json={"approved": False},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["error"]["code"] == "registry_error"

    missing = client.post(
        "/api/v2/models/TEST.NS/activate/v1",
        json={"approved": True},
    )
    assert missing.status_code == 400
    assert "No registry entry" in missing.json()["detail"]["error"]["message"]


def test_predict_without_active_model_is_conflict(monkeypatch):
    def no_active(symbol):
        raise ModelRegistryError("No active registered model")

    monkeypatch.setattr(
        research_routes.model_registry_service,
        "predict_with_active",
        no_active,
    )
    response = client.post("/api/v2/forecasting/predict/TEST.NS")
    assert response.status_code == 409
    assert response.json()["detail"]["error"]["code"] == "registry_unavailable"


def test_reports_listing_uses_configured_directories(tmp_path, monkeypatch):
    for name in (
        "EVALUATION_REPORT_DIR",
        "RETURN_REPORT_DIR",
        "BACKTEST_REPORT_DIR",
        "JOB_STATE_DIR",
    ):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "example.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(research_routes.settings, name, str(directory))

    response = client.get("/api/v2/reports")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload["categories"]) == {
        "walk_forward",
        "return_forecasting",
        "backtesting",
        "jobs",
    }
    assert payload["categories"]["walk_forward"][0]["name"] == "example.json"


def test_monitoring_pagination_validation():
    response = client.get(
        "/api/v2/monitoring/TEST.NS/predictions?page=0&page_size=20"
    )
    assert response.status_code == 422


def test_return_experiment_latest_report(tmp_path, monkeypatch):
    monkeypatch.setattr(
        research_routes.settings,
        "RETURN_REPORT_DIR",
        str(tmp_path),
    )
    (tmp_path / "TEST_NS_return_forecasting.json").write_text(
        json.dumps({"symbol": "TEST.NS", "experiment": "return_vs_absolute_price"}),
        encoding="utf-8",
    )
    response = client.get("/api/v2/forecasting/return-experiment/TEST.NS")
    assert response.status_code == 200
    assert response.json()["experiment"] == "return_vs_absolute_price"
