import json

import numpy as np
import pytest

from app.models.linear_regression import LinearRegressionModel
from app.services.data_service import data_service
from app.services.return_forecasting_service import (
    FAMILY_ABSOLUTE,
    FAMILY_LOG,
    FAMILY_SIMPLE,
    ZERO_RETURN_NAME,
    ReturnForecastingService,
)
from app.services.walk_forward_evaluation import (
    MODEL_NAMES,
    EvaluationConfig,
    WalkForwardEvaluationService,
)


class StaticDataService:
    def __init__(self, df):
        self.df = df.copy()

    def fetch_stock_data(self, symbol, period="2y"):
        return self.df.copy()

    def clean_data(self, df):
        return data_service.clean_data(df)


@pytest.fixture
def return_config():
    return EvaluationConfig(
        period="2y",
        folds=2,
        holdout_fraction=0.2,
        min_train_samples=60,
        min_validation_samples=12,
        min_holdout_samples=12,
        initial_train_fraction=0.5,
    )


@pytest.fixture
def linear_factories():
    return {name: LinearRegressionModel for name in MODEL_NAMES}


def test_reconstruction_formulas():
    current = np.array([100.0, 50.0])

    absolute = ReturnForecastingService._reconstruct_prices(
        FAMILY_ABSOLUTE, current, np.array([101.0, 49.0])
    )
    simple = ReturnForecastingService._reconstruct_prices(
        FAMILY_SIMPLE, current, np.array([0.01, -0.02])
    )
    log = ReturnForecastingService._reconstruct_prices(
        FAMILY_LOG, current, np.log(np.array([1.01, 0.98]))
    )

    assert absolute.tolist() == [101.0, 49.0]
    assert simple == pytest.approx([101.0, 49.0])
    assert log == pytest.approx([101.0, 49.0])


def test_return_experiment_matches_phase_two_boundaries_and_abstains(
    stock_data_factory,
    return_config,
    linear_factories,
    tmp_path,
):
    frame = stock_data_factory(rows=240)
    static_data = StaticDataService(frame)

    return_service = ReturnForecastingService(
        config=return_config,
        data_service_override=static_data,
        model_factories=linear_factories,
        report_dir=str(tmp_path),
    )
    report = return_service.evaluate_symbol(
        "TEST.NS", write_report=True
    )

    assert report["status"] == "completed"
    assert report["production_inference_changed"] is False
    assert set(report["families"]) == {
        FAMILY_ABSOLUTE,
        FAMILY_SIMPLE,
        FAMILY_LOG,
    }
    assert report["sample_counts"]["folds"] == 2

    # Every family uses the same baseline and the same validation rows.
    baseline_price_metrics = []
    validation_dates = {}
    for family, payload in report["families"].items():
        baseline = payload["final_holdout"]["models"][ZERO_RETURN_NAME]
        price_metrics = baseline["price_metrics"]
        assert price_metrics["signal_coverage"] == 0.0
        assert price_metrics["abstention_rate"] == 100.0
        assert price_metrics["directional_accuracy"] is None
        assert baseline["return_metrics"]["directional_accuracy"] is None
        baseline_price_metrics.append(price_metrics["rmse"])
        validation_dates[family] = payload["final_holdout"]["validation"][
            "target_dates"
        ]

    assert len({tuple(values) for values in validation_dates.values()}) == 1
    assert len(set(round(value, 8) for value in baseline_price_metrics)) == 1

    # The return experiment must use exactly the Phase 2 fold/holdout
    # boundaries when given the same data and configuration.
    walk_forward_service = WalkForwardEvaluationService(
        config=return_config,
        data_service_override=static_data,
        model_factories=linear_factories,
        report_dir=str(tmp_path),
    )
    walk_forward_report = walk_forward_service.evaluate_symbol(
        "TEST.NS", write_report=False
    )

    wf_folds = walk_forward_report["development_validation"]["folds"]
    return_folds = report["families"][FAMILY_ABSOLUTE]["folds"]
    assert len(wf_folds) == len(return_folds)
    for wf_fold, return_fold in zip(wf_folds, return_folds):
        assert wf_fold["train"]["start"] == return_fold["train"]["start"]
        assert wf_fold["train"]["end"] == return_fold["train"]["end"]
        assert (
            wf_fold["validation"]["start"]
            == return_fold["validation"]["start"]
        )
        assert (
            wf_fold["validation"]["end"] == return_fold["validation"]["end"]
        )

    wf_holdout = walk_forward_report["final_holdout"]["validation"]
    return_holdout = report["families"][FAMILY_ABSOLUTE]["final_holdout"][
        "validation"
    ]
    assert wf_holdout["dates"] == return_holdout["dates"]
    assert wf_holdout["target_dates"] == return_holdout["target_dates"]

    assert report["report_path"]
    with open(report["report_path"], encoding="utf-8") as handle:
        saved = json.load(handle)
    assert saved["schema_version"] == "1.0"
    assert saved["experiment"] == "return_vs_absolute_price"
    assert "recommendation" in saved["final_holdout_comparison"]


def test_return_experiment_report_contains_price_and_return_metrics(
    stock_data_factory,
    return_config,
    linear_factories,
    tmp_path,
):
    service = ReturnForecastingService(
        config=return_config,
        data_service_override=StaticDataService(stock_data_factory(rows=220)),
        model_factories=linear_factories,
        report_dir=str(tmp_path),
    )
    report = service.evaluate_symbol("TEST.NS", write_report=False)

    for family, payload in report["families"].items():
        for model_name in MODEL_NAMES:
            entry = payload["final_holdout"]["models"][model_name]
            assert entry["status"] == "ok"
            assert entry["price_metrics"]["n_samples"] > 0
            assert entry["return_metrics"]["n_samples"] > 0
            assert "nmae_pct" in entry["price_metrics"]
            assert "relative_return_mae" in entry["return_metrics"]
            assert "signal_coverage" in entry["return_metrics"]

        aggregate = payload["aggregated"]["models"][ZERO_RETURN_NAME]
        assert aggregate["price_metrics"]["directional_accuracy"] is None
        assert aggregate["return_metrics"]["signal_coverage"] == 0.0
