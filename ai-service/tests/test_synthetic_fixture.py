from pathlib import Path

import pandas as pd

from app.services.data_service import data_service
from app.services.walk_forward_evaluation import (
    EvaluationConfig,
    build_evaluation_dataset,
    generate_walk_forward_folds,
    split_development_holdout,
)

FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_ohlcv.csv"


def test_synthetic_fixture_supports_offline_walk_forward_setup():
    """The repository includes artificial OHLCV data for offline tests."""

    raw = pd.read_csv(FIXTURE)
    assert len(raw) == 320
    assert list(raw.columns) == [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    clean = data_service.clean_data(raw)
    dataset = build_evaluation_dataset(clean)
    config = EvaluationConfig(
        period="synthetic",
        folds=3,
        holdout_fraction=0.2,
        min_train_samples=60,
        min_validation_samples=10,
        min_holdout_samples=10,
        initial_train_fraction=0.5,
    )
    development, holdout, holdout_info = split_development_holdout(
        dataset, config
    )
    folds, fold_info = generate_walk_forward_folds(development, config)

    assert not development.empty
    assert not holdout.empty
    assert holdout_info["holdout_rows"] >= config.min_holdout_samples
    assert len(folds) == fold_info["folds_used"] == 3
    assert all(
        fold.train_target_end < fold.validation_target_start
        for fold in folds
    )
