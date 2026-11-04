import numpy as np
import pytest

from app.services.evaluation_metrics import (
    calculate_metrics,
    calculate_return_metrics,
    compare_metrics_to_baseline,
)


class TestEvaluationMetrics:
    def test_perfect_predictions(self):
        metrics = calculate_metrics(
            y_true=[10.0, 20.0, 30.0],
            y_pred=[10.0, 20.0, 30.0],
            current_prices=[9.0, 19.0, 29.0],
        )

        assert metrics["n_samples"] == 3
        assert metrics["directional_samples"] == 3
        assert metrics["signal_samples"] == 3
        assert metrics["directional_signal_samples"] == 3
        assert metrics["directional_correct"] == 3
        assert metrics["signal_coverage"] == 100.0
        assert metrics["abstention_rate"] == 0.0
        assert metrics["mae"] == 0.0
        assert metrics["mse"] == 0.0
        assert metrics["rmse"] == 0.0
        assert metrics["r2_score"] == 1.0
        assert metrics["smape"] == 0.0
        assert metrics["mape"] == 0.0
        assert metrics["directional_accuracy"] == 100.0

    def test_known_errors_and_direction(self):
        y_true = np.array([10.0, 20.0, 30.0])
        y_pred = np.array([11.0, 19.0, 31.0])
        current = np.array([9.0, 19.0, 29.0])

        metrics = calculate_metrics(y_true, y_pred, current)

        expected_mae = 1.0
        expected_rmse = 1.0
        expected_smape = np.mean(
            [2 * 1 / 21, 2 * 1 / 39, 2 * 1 / 61]
        ) * 100
        expected_r2 = 1 - 3 / np.sum((y_true - y_true.mean()) ** 2)

        assert metrics["mae"] == pytest.approx(expected_mae)
        assert metrics["rmse"] == pytest.approx(expected_rmse)
        assert metrics["smape"] == pytest.approx(expected_smape, rel=1e-6)
        assert metrics["r2_score"] == pytest.approx(expected_r2, rel=1e-6)

        # The middle prediction is exactly the current price, so it is an
        # abstention. Both remaining signals are directionally correct.
        assert metrics["signal_samples"] == 2
        assert metrics["directional_signal_samples"] == 2
        assert metrics["directional_correct"] == 2
        assert metrics["directional_accuracy"] == pytest.approx(
            100.0, rel=1e-6
        )
        assert metrics["signal_coverage"] == pytest.approx(66.666667, rel=1e-6)
        assert metrics["abstention_rate"] == pytest.approx(
            33.333333, rel=1e-6
        )

    def test_zero_values_and_constant_targets_do_not_produce_nan(self):
        metrics = calculate_metrics(
            y_true=[0.0, 0.0, 10.0],
            y_pred=[0.0, 0.0, 9.0],
            current_prices=[0.0, 0.0, 9.0],
        )

        for key in (
            "mae",
            "rmse",
            "smape",
            "r2_score",
            "directional_accuracy",
        ):
            assert metrics[key] is None or np.isfinite(metrics[key])
        assert metrics["smape"] == pytest.approx(2 * 1 / 19 * 100 / 3)

        # The only actual move has an abstaining prediction.
        assert metrics["directional_samples"] == 1
        assert metrics["signal_samples"] == 0
        assert metrics["directional_accuracy"] is None
        assert metrics["signal_coverage"] == 0.0
        assert metrics["abstention_rate"] == 100.0

        constant_metrics = calculate_metrics(
            y_true=[5.0, 5.0, 5.0],
            y_pred=[5.0, 5.0, 5.0],
            current_prices=[4.0, 4.0, 4.0],
        )
        assert constant_metrics["r2_score"] is None
        assert constant_metrics["mae"] == 0.0
        assert constant_metrics["directional_accuracy"] == 100.0

    def test_empty_and_non_finite_inputs_are_safe(self):
        empty = calculate_metrics([], [], [])
        assert empty["n_samples"] == 0
        assert empty["mae"] is None
        assert empty["rmse"] is None
        assert empty["r2_score"] is None
        assert empty["smape"] is None
        assert empty["directional_accuracy"] is None
        assert empty["signal_coverage"] is None

        metrics = calculate_metrics(
            y_true=[1.0, np.nan, 3.0, np.inf],
            y_pred=[1.0, 2.0, 4.0, 5.0],
            current_prices=[0.5, 1.5, 2.5, 4.5],
        )
        assert metrics["n_samples"] == 2
        assert metrics["mae"] == pytest.approx(0.5)
        assert metrics["directional_accuracy"] == pytest.approx(100.0)

    def test_directional_accuracy_ignores_zero_actual_moves(self):
        metrics = calculate_metrics(
            y_true=[10.0, 10.0, 12.0],
            y_pred=[11.0, 9.0, 13.0],
            current_prices=[10.0, 10.0, 10.0],
        )

        assert metrics["directional_samples"] == 1
        assert metrics["signal_samples"] == 3
        assert metrics["directional_signal_samples"] == 1
        assert metrics["directional_accuracy"] == 100.0
        assert metrics["signal_coverage"] == 100.0

    def test_abstaining_baseline_has_undefined_directional_accuracy(self):
        metrics = calculate_metrics(
            y_true=[11.0, 9.0, 12.0],
            y_pred=[10.0, 10.0, 10.0],
            current_prices=[10.0, 10.0, 10.0],
        )

        assert metrics["directional_samples"] == 3
        assert metrics["signal_samples"] == 0
        assert metrics["directional_signal_samples"] == 0
        assert metrics["directional_accuracy"] is None
        assert metrics["signal_coverage"] == 0.0
        assert metrics["abstention_rate"] == 100.0

    def test_normalized_and_relative_metrics(self):
        metrics = calculate_metrics(
            y_true=[11.0, 21.0, 31.0],
            y_pred=[10.0, 20.0, 30.0],
            current_prices=[10.0, 20.0, 30.0],
        )

        assert metrics["mean_current_price"] == pytest.approx(20.0)
        assert metrics["mean_abs_actual_change"] == pytest.approx(1.0)
        assert metrics["nmae_pct"] == pytest.approx(5.0)
        assert metrics["nrmse_pct"] == pytest.approx(5.0)
        assert metrics["mase_vs_random_walk"] == pytest.approx(1.0)

    def test_return_metrics_treat_zero_return_as_abstention(self):
        metrics = calculate_return_metrics(
            y_true=[0.01, -0.02, 0.03],
            y_pred=[0.0, -0.01, 0.02],
        )

        assert metrics["return_mae"] == pytest.approx(
            np.mean([0.01, 0.01, 0.01])
        )
        assert metrics["directional_samples"] == 3
        assert metrics["signal_samples"] == 2
        assert metrics["directional_accuracy"] == 100.0
        assert metrics["signal_coverage"] == pytest.approx(66.666667, rel=1e-6)
        assert metrics["mean_abs_actual_return"] == pytest.approx(0.02)
        assert metrics["relative_return_mae"] == pytest.approx(0.5)

    def test_compare_metrics_to_baseline(self):
        candidate = {
            "mae": 1.0,
            "rmse": 2.0,
            "smape": 5.0,
            "directional_accuracy": 60.0,
            "signal_coverage": 80.0,
        }
        baseline = {
            "mae": 2.0,
            "rmse": 4.0,
            "smape": 10.0,
            "directional_accuracy": 50.0,
            "signal_coverage": 70.0,
        }

        comparison = compare_metrics_to_baseline(candidate, baseline)

        assert comparison["beats_baseline"] is True
        assert comparison["beats_baseline_on_rmse"] is True
        assert comparison["beats_baseline_on_mae"] is True
        assert comparison["beats_baseline_on_smape"] is True
        assert comparison["directional_accuracy_comparable"] is True
        assert comparison["beats_baseline_on_directional_accuracy"] is True
        assert comparison["mae_improvement_pct"] == pytest.approx(50.0)
        assert comparison["rmse_improvement_pct"] == pytest.approx(50.0)
        assert comparison["smape_improvement_pct"] == pytest.approx(50.0)
        assert comparison["directional_accuracy_delta_pp"] == pytest.approx(10.0)
        assert comparison["signal_coverage_delta_pp"] == pytest.approx(10.0)

    def test_compare_metrics_does_not_invent_directional_win(self):
        comparison = compare_metrics_to_baseline(
            {"mae": 1.0, "rmse": 2.0, "smape": 5.0, "directional_accuracy": 55.0},
            {
                "mae": 2.0,
                "rmse": 4.0,
                "smape": 10.0,
                "directional_accuracy": None,
                "signal_coverage": 0.0,
            },
        )

        assert comparison["beats_baseline_on_directional_accuracy"] is False
        assert comparison["directional_accuracy_comparable"] is False
        assert comparison["directional_accuracy_delta_pp"] is None

    def test_compare_metrics_handles_zero_baseline(self):
        comparison = compare_metrics_to_baseline(
            {"mae": 0.0, "rmse": 0.0, "smape": 0.0, "directional_accuracy": 0.0},
            {"mae": 0.0, "rmse": 0.0, "smape": 0.0, "directional_accuracy": 0.0},
        )

        assert comparison["beats_baseline"] is False
        assert comparison["mae_improvement_pct"] is None
        assert comparison["rmse_improvement_pct"] is None
        assert comparison["smape_improvement_pct"] is None
        assert comparison["directional_accuracy_delta_pp"] == pytest.approx(0.0)
