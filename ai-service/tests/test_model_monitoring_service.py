import json

import pandas as pd
import pytest

from app.services.data_service import data_service
from app.services.model_monitoring_service import ModelMonitoringService


class StaticDataService:
    def __init__(self, df):
        self.df = df.copy()

    def fetch_stock_data(self, symbol, period="6mo"):
        return self.df.copy()

    def clean_data(self, df):
        return data_service.clean_data(df)


@pytest.fixture
def monitoring(stock_data_factory, tmp_path):
    frame = stock_data_factory(320)
    return (
        ModelMonitoringService(
            monitoring_dir=str(tmp_path / "monitoring"),
            data_service_override=StaticDataService(frame),
        ),
        frame,
    )


def _prediction(frame, feature_index=0):
    current = float(frame.iloc[feature_index]["Close"])
    predicted = current * 1.01
    return {
        "model_id": "TEST.NS:v1",
        "model_version": "v1",
        "feature_timestamp": str(
            pd.Timestamp(frame.iloc[feature_index]["Date"]).date()
        ),
        "current_price": current,
        "predicted_price": predicted,
        "predicted_return": 0.01,
        "signal": "BUY",
    }


def test_record_and_update_prediction(monitoring):
    service, frame = monitoring
    prediction = _prediction(frame)
    record = service.record_prediction("TEST.NS", prediction)

    assert record["status"] == "pending"
    listed = service.list_predictions("TEST.NS")
    assert listed["total"] == 1

    update = service.update_actuals("TEST.NS")
    assert update["updated"] == 1
    listed = service.list_predictions("TEST.NS")
    item = listed["items"][0]
    assert item["status"] == "completed"
    assert item["actual_price"] == pytest.approx(
        float(frame.iloc[1]["Close"])
    )
    assert item["actual_date"] == str(
        pd.Timestamp(frame.iloc[1]["Date"]).date()
    )

    summary = service.monitoring_summary("TEST.NS")
    assert summary["record_counts"]["total"] == 1
    assert summary["record_counts"]["completed"] == 1
    assert summary["tracking_metrics"]["metrics"]["n_samples"] == 1
    assert summary["data_freshness"]["status"] == "ok"


def test_abstaining_prediction_has_no_artificial_directional_accuracy(monitoring):
    service, frame = monitoring
    prediction = _prediction(frame)
    prediction["predicted_price"] = prediction["current_price"]
    prediction["predicted_return"] = 0.0
    prediction["signal"] = "HOLD"
    service.record_prediction("TEST.NS", prediction)
    service.update_actuals("TEST.NS")

    summary = service.monitoring_summary("TEST.NS")
    metrics = summary["tracking_metrics"]["metrics"]
    assert metrics["directional_accuracy"] is None
    assert metrics["signal_coverage"] == 0.0
    assert metrics["abstention_rate"] == 100.0


def test_pagination_and_drift(monitoring):
    service, frame = monitoring
    for index in range(5):
        service.record_prediction("TEST.NS", _prediction(frame, index))

    page = service.list_predictions("TEST.NS", page=2, page_size=2)
    assert page["total"] == 5
    assert page["total_pages"] == 3
    assert len(page["items"]) == 2

    drift = service.drift_report("TEST.NS")
    assert drift["drift"]["status"] == "ok"
    assert drift["drift"]["reference_rows"] > 0
    assert len(drift["drift"]["features"]) == 16
    assert drift["drift"]["drift_detected"] is not None

    with pytest.raises(ValueError):
        service.list_predictions("TEST.NS", page=0)
    with pytest.raises(ValueError):
        service.list_predictions("TEST.NS", page_size=1000)


def test_monitoring_store_is_jsonl(monitoring):
    service, frame = monitoring
    service.record_prediction("TEST.NS", _prediction(frame))
    path = service._path("TEST.NS")
    with open(path, encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    assert len(records) == 1
    assert records[0]["symbol"] == "TEST.NS"
