from datetime import datetime, timezone

import numpy as np
import pytest

from app.services.data_service import data_service
from app.services.evaluation_metrics import calculate_metrics
from app.services.feature_engineering import feature_engineering
from app.services.walk_forward_evaluation import (
    BASELINE_NAME,
    ENSEMBLE_NAME,
    MODEL_NAMES,
    EvaluationConfig,
    InsufficientEvaluationData,
    WalkForwardEvaluationService,
    build_evaluation_dataset,
    generate_walk_forward_folds,
    split_development_holdout,
)
from app.models.svr_model import SVRModel


EXPECTED_FEATURE_COLUMNS = [
    "Open", "High", "Low", "Close", "Volume",
    "SMA_10", "SMA_20", "SMA_50",
    "RSI_14",
    "MACD", "Signal_Line",
    "Bollinger_Upper", "Bollinger_Lower",
    "Price_Change", "Volume_Change", "High_Low_Range",
]
CLOSE_INDEX = EXPECTED_FEATURE_COLUMNS.index("Close")


class StaticDataService:
    def __init__(self, df):
        self.df = df.copy()

    def fetch_stock_data(self, symbol, period="2y"):
        return self.df.copy()

    def clean_data(self, df):
        return data_service.clean_data(df)


class OffsetCloseModel:
    def __init__(self, offset=0.0):
        self.offset = float(offset)
        self.train_X = None
        self.train_y = None

    def train(self, X_train, y_train):
        self.train_X = np.array(X_train, copy=True)
        self.train_y = np.array(y_train, copy=True)

    def predict(self, X):
        return np.asarray(X, dtype=float)[:, CLOSE_INDEX] + self.offset


class TrainingMeanModel:
    def train(self, X_train, y_train):
        self.mean_ = float(np.mean(y_train))

    def predict(self, X):
        return np.full(len(X), self.mean_, dtype=float)


class BrokenModel:
    def train(self, X_train, y_train):
        raise RuntimeError("intentional fold failure")

    def predict(self, X):
        return np.zeros(len(X), dtype=float)


def make_test_config(folds=3):
    return EvaluationConfig(
        period="2y",
        folds=folds,
        holdout_fraction=0.2,
        min_train_samples=60,
        min_validation_samples=10,
        min_holdout_samples=10,
        initial_train_fraction=0.5,
    )


def fake_factories(offsets=None):
    offsets = offsets or [0.0, 0.5, 1.0, 1.5, 2.0]
    names = list(MODEL_NAMES)
    return {
        names[0]: lambda: OffsetCloseModel(offsets[0]),
        names[1]: lambda: OffsetCloseModel(offsets[1]),
        names[2]: lambda: OffsetCloseModel(offsets[2]),
        names[3]: lambda: OffsetCloseModel(offsets[3]),
        names[4]: lambda: OffsetCloseModel(offsets[4]),
    }


def make_service(df, model_factories=None, now_provider=None):
    return WalkForwardEvaluationService(
        config=make_test_config(),
        data_service_override=StaticDataService(df),
        model_factories=model_factories or fake_factories(),
        report_dir=None,
        now_provider=now_provider,
    )


def prepared_split(df):
    clean = data_service.clean_data(df)
    dataset = build_evaluation_dataset(clean)
    development, holdout, holdout_info = split_development_holdout(
        dataset, make_test_config()
    )
    folds, fold_info = generate_walk_forward_folds(
        development, make_test_config()
    )
    return dataset, development, holdout, holdout_info, folds, fold_info


class TestWalkForwardFolds:
    def test_folds_are_chronological_non_overlapping_and_expanding(
        self, stock_data_factory
    ):
        df = stock_data_factory(400)
        (
            dataset,
            development,
            holdout,
            holdout_info,
            folds,
            fold_info,
        ) = prepared_split(df)

        assert len(folds) == 3
        assert fold_info["folds_used"] == 3
        assert development["Date"].is_monotonic_increasing
        assert development["Target_Date"].is_monotonic_increasing
        assert holdout["Target_Date"].min() > development["Target_Date"].max()

        previous_validation_end = -1
        previous_train_size = 0
        for fold in folds:
            train_indices = fold.train_indices
            validation_indices = fold.validation_indices

            # Training is a contiguous prefix, validation is a contiguous
            # later block, and the blocks never overlap.
            assert train_indices.min() == 0
            assert np.array_equal(
                train_indices, np.arange(len(train_indices))
            )
            assert validation_indices.min() > train_indices.max()
            assert validation_indices.min() > previous_validation_end
            assert len(train_indices) > previous_train_size

            # Dates, not row positions, prove the temporal ordering.
            assert fold.train_end < fold.validation_start
            assert fold.train_target_end < fold.validation_target_start
            assert fold.validation_target_start > fold.validation_start

            previous_validation_end = int(validation_indices.max())
            previous_train_size = len(train_indices)

        # Validation folds cover the development period after the initial
        # training window exactly once.
        covered = np.concatenate([fold.validation_indices for fold in folds])
        assert len(np.unique(covered)) == len(covered)
        assert covered.min() == fold_info["initial_validation_start_index"]
        assert covered.max() == len(development) - 1
        assert len(covered) == len(development) - covered.min()

    def test_fold_count_is_reduced_when_data_is_limited(
        self, stock_data_factory
    ):
        df = stock_data_factory(250)
        dataset = build_evaluation_dataset(data_service.clean_data(df))
        config = make_test_config(folds=10)
        development, _, _ = split_development_holdout(dataset, config)
        folds, info = generate_walk_forward_folds(development, config)

        assert info["requested_folds"] == 10
        assert info["folds_used"] < 10
        assert info["folds_reduced"] is True
        assert len(folds) == info["folds_used"]

    def test_insufficient_history_is_reported(self, stock_data_factory):
        df = stock_data_factory(80)
        service = make_service(df)

        with pytest.raises(InsufficientEvaluationData, match="Not enough"):
            service.evaluate_symbol("TEST.NS", write_report=False)

    def test_trading_day_gaps_use_actual_next_available_date(
        self, stock_data_factory
    ):
        df = stock_data_factory(220).drop(index=100).reset_index(drop=True)
        dataset = build_evaluation_dataset(data_service.clean_data(df))

        feature_date = df["Date"].iloc[99]
        expected_target_date = df["Date"].iloc[100]
        row = dataset.featured_df[
            dataset.featured_df["Date"] == feature_date
        ].iloc[0]

        assert row["Target_Date"] == expected_target_date
        assert (dataset.featured_df["Target_Date"] > dataset.featured_df["Date"]).all()
        assert dataset.featured_df["Target_Date"].is_unique

    def test_features_do_not_use_future_rows(self, stock_data_factory):
        df = stock_data_factory(240)
        cutoff = 180
        full_features = feature_engineering.transform_features(df)
        prefix_features = feature_engineering.transform_features(
            df.iloc[:cutoff]
        )

        cutoff_date = df["Date"].iloc[cutoff - 1]
        full_row = full_features[
            full_features["Date"] == cutoff_date
        ].iloc[0]
        prefix_row = prefix_features.iloc[-1]

        assert prefix_row["Date"] == cutoff_date
        np.testing.assert_allclose(
            prefix_row[EXPECTED_FEATURE_COLUMNS].to_numpy(dtype=float),
            full_row[EXPECTED_FEATURE_COLUMNS].to_numpy(dtype=float),
        )


class TestWalkForwardEvaluation:
    def test_baseline_is_current_close_on_identical_validation_rows(
        self, stock_data_factory
    ):
        df = stock_data_factory(400)
        service = make_service(df)
        report = service.evaluate_symbol("TEST.NS", write_report=False)

        assert report["status"] == "completed"
        assert report["data"]["feature_columns"] == EXPECTED_FEATURE_COLUMNS
        assert report["development_validation"]["fold_generation"]["folds_used"] == 3

        fold_reports = report["development_validation"]["folds"]
        assert len(fold_reports) == 3

        for fold_report in fold_reports:
            validation = fold_report["validation"]
            current = np.asarray(validation["current_close"], dtype=float)
            actual = np.asarray(validation["actual_next_close"], dtype=float)
            baseline_prediction = np.asarray(
                validation["predictions"][BASELINE_NAME], dtype=float
            )
            np.testing.assert_allclose(baseline_prediction, current)

            expected = calculate_metrics(actual, current, current)
            actual_metrics = fold_report["models"][BASELINE_NAME]["metrics"]
            for key in (
                "mae",
                "rmse",
                "r2_score",
                "smape",
                "directional_accuracy",
                "signal_coverage",
                "abstention_rate",
            ):
                assert actual_metrics[key] == expected[key]
            assert actual_metrics["n_samples"] == len(validation["dates"])
            assert actual_metrics["directional_accuracy"] is None
            assert actual_metrics["signal_coverage"] == 0.0
            assert actual_metrics["abstention_rate"] == 100.0

        pooled_actual = np.concatenate(
            [
                np.asarray(fold["validation"]["actual_next_close"], dtype=float)
                for fold in fold_reports
            ]
        )
        pooled_current = np.concatenate(
            [
                np.asarray(fold["validation"]["current_close"], dtype=float)
                for fold in fold_reports
            ]
        )
        pooled_expected = calculate_metrics(
            pooled_actual, pooled_current, pooled_current
        )
        pooled_actual_metrics = report["development_validation"]["aggregated"][
            BASELINE_NAME
        ]["metrics"]
        for key in (
            "mae",
            "rmse",
            "r2_score",
            "smape",
            "directional_accuracy",
            "signal_coverage",
            "abstention_rate",
        ):
            assert pooled_actual_metrics[key] == pooled_expected[key]
        assert pooled_actual_metrics["directional_accuracy"] is None
        assert pooled_actual_metrics["signal_coverage"] == 0.0
        assert pooled_actual_metrics["abstention_rate"] == 100.0

        holdout = report["final_holdout"]
        current = np.asarray(holdout["validation"]["current_close"], dtype=float)
        actual = np.asarray(holdout["validation"]["actual_next_close"], dtype=float)
        baseline_prediction = np.asarray(
            holdout["validation"]["predictions"][BASELINE_NAME], dtype=float
        )
        np.testing.assert_allclose(baseline_prediction, current)
        assert holdout["models"][BASELINE_NAME]["metrics"] == calculate_metrics(
            actual, current, current
        )

    def test_feature_columns_and_sample_counts_are_identical_for_all_models(
        self, stock_data_factory
    ):
        df = stock_data_factory(400)
        report = make_service(df).evaluate_symbol("TEST.NS", write_report=False)

        for fold_report in report["development_validation"]["folds"]:
            validation_samples = fold_report["validation"]["samples"]
            for name in MODEL_NAMES + (BASELINE_NAME, ENSEMBLE_NAME):
                entry = fold_report["models"][name]
                assert entry["train_features"] == len(EXPECTED_FEATURE_COLUMNS)
                assert entry["metrics"]["n_samples"] == validation_samples
                assert len(
                    fold_report["validation"]["predictions"][name]
                ) == validation_samples

    def test_svr_scaler_is_fit_only_on_each_folds_training_rows(
        self, stock_data_factory
    ):
        df = stock_data_factory(400)
        _, development, _, _, folds, _ = prepared_split(df)

        factories = fake_factories()
        factories["svr"] = SVRModel
        report = make_service(df, model_factories=factories).evaluate_symbol(
            "TEST.NS", write_report=False
        )

        reported_means = []
        for fold, fold_report in zip(
            folds, report["development_validation"]["folds"]
        ):
            svr = fold_report["models"]["svr"]
            assert svr["status"] == "ok"
            preprocessing = svr["preprocessing"]
            assert preprocessing["fit_on"] == "fold_training_data_only"
            assert preprocessing["fit_samples"] == len(fold.train_indices)
            assert preprocessing["feature_columns"] == EXPECTED_FEATURE_COLUMNS

            expected_mean = (
                development.iloc[fold.train_indices][
                    EXPECTED_FEATURE_COLUMNS
                ]
                .to_numpy(dtype=float)
                .mean(axis=0)
            )
            reported_mean = np.asarray(
                preprocessing["feature_means"], dtype=float
            )
            np.testing.assert_allclose(reported_mean, expected_mean, atol=1e-5)
            reported_means.append(reported_mean)

        # A scaler reused across folds would produce identical means.  The
        # expanding training windows must produce different scalers.
        assert not np.allclose(reported_means[0], reported_means[1])
        assert (
            report["development_validation"]["folds"][1]["models"]["svr"][
                "preprocessing"
            ]["fit_samples"]
            > report["development_validation"]["folds"][0]["models"]["svr"][
                "preprocessing"
            ]["fit_samples"]
        )

    def test_final_holdout_is_isolated_from_development_selection(
        self, stock_data_factory
    ):
        df = stock_data_factory(400)
        report = make_service(df).evaluate_symbol("TEST.NS", write_report=False)

        holdout = report["final_holdout"]
        development = report["development_validation"]
        selection = development["model_selection"]

        assert selection["holdout_used_for_selection"] is False
        assert selection["selection_locked_before_holdout"] is True
        assert holdout["selection_locked_before_holdout"] is True
        assert holdout["train"]["target_end"] < holdout["validation"]["target_start"]
        assert holdout["train"]["end"] < holdout["validation"]["start"]

        for fold_report in development["folds"]:
            assert (
                fold_report["validation"]["target_end"]
                < holdout["validation"]["target_start"]
            )
            assert (
                fold_report["validation"]["end"] < holdout["validation"]["start"]
            )

        selected = selection["selected_model"]
        assert selected is not None
        assert selected in [entry["model"] for entry in selection["ranking_development_ml_and_ensemble"]]
        assert (
            selection["selected_model_development_metrics"]
            == development["aggregated"][selected]["metrics"]
        )
        assert (
            report["best_performing_model"]["final_holdout_metrics"]
            == holdout["models"][selected]["metrics"]
        )

    def test_failed_fold_is_reported_not_silently_dropped(
        self, stock_data_factory
    ):
        df = stock_data_factory(400)
        factories = fake_factories()
        factories["svr"] = BrokenModel
        report = make_service(df, model_factories=factories).evaluate_symbol(
            "TEST.NS", write_report=False
        )

        fold_reports = report["development_validation"]["folds"]
        assert len(fold_reports) == 3
        assert any(fold["status"] != "ok" for fold in fold_reports)
        assert any(
            "intentional fold failure" in (error.get("error") or "")
            for fold in fold_reports
            for error in fold["errors"]
        )

        aggregated_svr = report["development_validation"]["aggregated"]["svr"]
        assert aggregated_svr["status"] == "incomplete"
        assert aggregated_svr["metrics"] is None
        assert aggregated_svr["missing_folds"]
        assert (
            report["development_validation"]["aggregated"][ENSEMBLE_NAME][
                "status"
            ]
            == "incomplete"
        )

    def test_repeated_runs_are_deterministic(self, stock_data_factory):
        df = stock_data_factory(400)
        fixed_time = datetime(2026, 1, 1, tzinfo=timezone.utc)

        def fixed_now():
            return fixed_time

        service = make_service(df, now_provider=fixed_now)
        first = service.evaluate_symbol("TEST.NS", write_report=False)
        second = service.evaluate_symbol("TEST.NS", write_report=False)

        assert first == second
        assert first["data"]["data_fingerprint_sha256"] == second["data"][
            "data_fingerprint_sha256"
        ]
        assert first["generated_at"] == fixed_time.isoformat()

    def test_reproducibility_metadata_and_synthetic_source(
        self, stock_data_factory
    ):
        df = stock_data_factory(400)
        service = make_service(df)
        service.data_service.source_label = "synthetic_test_data"
        service.data_service.is_synthetic = True
        report = service.evaluate_symbol("TEST.NS", write_report=False)

        reproducibility = report["reproducibility"]
        assert reproducibility["symbol"] == "TEST.NS"
        assert reproducibility["random_seed"] == 42
        assert reproducibility["dataset_period"] == "2y"
        assert reproducibility["data_source"] == "synthetic_test_data"
        assert reproducibility["is_synthetic"] is True
        assert len(reproducibility["evaluation_config_sha256"]) == 64
        assert reproducibility["feature_schema"] == EXPECTED_FEATURE_COLUMNS
        assert report["data"]["is_synthetic"] is True
        assert report["data"]["source"] == "synthetic_test_data"

    def test_ensemble_is_equal_weight_and_production_behavior_is_unchanged(
        self, stock_data_factory
    ):
        df = stock_data_factory(400)
        report = make_service(df).evaluate_symbol("TEST.NS", write_report=False)

        ensemble = report["ensemble_evaluation"]
        assert ensemble["equal_weight"] is True
        assert ensemble["production_ensemble_behavior_changed"] is False
        assert set(ensemble["weights"]) == set(MODEL_NAMES)
        assert all(
            weight == pytest.approx(1.0 / len(MODEL_NAMES))
            for weight in ensemble["weights"].values()
        )

        # The recorded ensemble prediction is the arithmetic mean of the five
        # component predictions on the same validation rows.
        for fold_report in report["development_validation"]["folds"]:
            predictions = fold_report["validation"]["predictions"]
            component_mean = np.mean(
                np.vstack([predictions[name] for name in MODEL_NAMES]),
                axis=0,
            )
            np.testing.assert_allclose(
                np.asarray(predictions[ENSEMBLE_NAME], dtype=float),
                component_mean,
                atol=1e-5,
            )
