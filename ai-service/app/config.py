import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME: str = "AI Stock Prediction Service"
    APP_VERSION: str = "1.0.0"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"

    CORS_ORIGINS: list = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
    ]

    SAVED_MODELS_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "saved_models")

    TRAINING_PERIOD: str = "1y"
    TRAIN_TEST_SPLIT: float = 0.2
    RANDOM_STATE: int = 42

    # Phase 2 evaluation settings. These are intentionally separate from the
    # production training settings so walk-forward evaluation can use a longer
    # history without changing existing training or prediction behavior.
    EVALUATION_PERIOD: str = os.getenv("EVALUATION_PERIOD", "2y")
    EVALUATION_FOLDS: int = int(os.getenv("EVALUATION_FOLDS", "5"))
    EVALUATION_HOLDOUT_FRACTION: float = float(
        os.getenv("EVALUATION_HOLDOUT_FRACTION", "0.2")
    )
    EVALUATION_MIN_TRAIN_SAMPLES: int = int(
        os.getenv("EVALUATION_MIN_TRAIN_SAMPLES", "60")
    )
    EVALUATION_MIN_VALIDATION_SAMPLES: int = int(
        os.getenv("EVALUATION_MIN_VALIDATION_SAMPLES", "10")
    )
    EVALUATION_MIN_HOLDOUT_SAMPLES: int = int(
        os.getenv("EVALUATION_MIN_HOLDOUT_SAMPLES", "10")
    )
    EVALUATION_INITIAL_TRAIN_FRACTION: float = float(
        os.getenv("EVALUATION_INITIAL_TRAIN_FRACTION", "0.5")
    )
    EVALUATION_REPORT_DIR: str = os.getenv(
        "EVALUATION_REPORT_DIR",
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "evaluation_reports",
        ),
    )

    # Phase 2.1+ research/storage settings. Reports and registry artifacts are
    # kept separate from saved_models so research experiments never overwrite
    # active production artifacts.
    SERVICE_ROOT: str = os.path.dirname(os.path.dirname(__file__))
    RESEARCH_REPORT_DIR: str = os.getenv(
        "RESEARCH_REPORT_DIR",
        os.path.join(SERVICE_ROOT, "research_reports"),
    )
    RETURN_REPORT_DIR: str = os.getenv(
        "RETURN_REPORT_DIR",
        os.path.join(SERVICE_ROOT, "research_reports", "return_forecasting"),
    )
    BACKTEST_REPORT_DIR: str = os.getenv(
        "BACKTEST_REPORT_DIR",
        os.path.join(SERVICE_ROOT, "backtesting_reports"),
    )
    MODEL_REGISTRY_DIR: str = os.getenv(
        "MODEL_REGISTRY_DIR",
        os.path.join(SERVICE_ROOT, "model_registry"),
    )
    MONITORING_DIR: str = os.getenv(
        "MONITORING_DIR",
        os.path.join(SERVICE_ROOT, "monitoring"),
    )
    JOB_STATE_DIR: str = os.getenv(
        "JOB_STATE_DIR",
        os.path.join(SERVICE_ROOT, "research_reports", "jobs"),
    )
    JOB_MAX_WORKERS: int = int(os.getenv("JOB_MAX_WORKERS", "2"))
    JOB_TIMEOUT_SECONDS: int = int(os.getenv("JOB_TIMEOUT_SECONDS", "1800"))

    BACKTEST_STARTING_CAPITAL: float = float(
        os.getenv("BACKTEST_STARTING_CAPITAL", "100000")
    )
    BACKTEST_TRANSACTION_COST_BPS: float = float(
        os.getenv("BACKTEST_TRANSACTION_COST_BPS", "5")
    )
    BACKTEST_SLIPPAGE_BPS: float = float(
        os.getenv("BACKTEST_SLIPPAGE_BPS", "5")
    )
    BACKTEST_MAX_CAPITAL_ALLOCATION: float = float(
        os.getenv("BACKTEST_MAX_CAPITAL_ALLOCATION", "1.0")
    )
    BACKTEST_BUY_THRESHOLD: float = float(
        os.getenv("BACKTEST_BUY_THRESHOLD", "0.005")
    )
    BACKTEST_SELL_THRESHOLD: float = float(
        os.getenv("BACKTEST_SELL_THRESHOLD", "-0.005")
    )
    RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.0"))
    TRADING_DAYS_PER_YEAR: int = int(os.getenv("TRADING_DAYS_PER_YEAR", "252"))

    DRIFT_PSI_THRESHOLD: float = float(os.getenv("DRIFT_PSI_THRESHOLD", "0.2"))
    DRIFT_REFERENCE_ROWS: int = int(os.getenv("DRIFT_REFERENCE_ROWS", "120"))
    DRIFT_RECENT_ROWS: int = int(os.getenv("DRIFT_RECENT_ROWS", "30"))

settings = Settings()
