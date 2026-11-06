import os

import numpy as np
import pandas as pd
import pytest

# Configure an internal service token before app.config is imported. Tests use
# the same header the Express gateway sends in production.
os.environ.setdefault("SERVICE_AUTH_TOKEN", "test-internal-service-token-0123456789")
os.environ.setdefault("ENVIRONMENT", "test")


@pytest.fixture
def stock_data_factory():
    """Create deterministic OHLCV data without network access."""

    def make_stock_data(rows: int = 90, start: str = "2026-01-01") -> pd.DataFrame:
        dates = pd.bdate_range(start, periods=rows)
        close = 100 + np.linspace(0, 50, rows) + np.sin(np.arange(rows) / 3) * 2

        return pd.DataFrame(
            {
                "Date": dates,
                "Open": close - 0.5,
                "High": close + 1.0,
                "Low": close - 1.0,
                "Close": close,
                "Volume": np.full(rows, 1_000_000.0),
            }
        )

    return make_stock_data
