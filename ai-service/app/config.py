import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


class Settings:
    APP_NAME: str = "AI Stock Prediction Service"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", 8000))
    # Secure by default: debug output must be explicitly enabled.
    DEBUG: bool = _env_bool("DEBUG", False)
    ENABLE_DOCS: bool = _env_bool("ENABLE_DOCS", False)

    # Shared secret used by the Express backend. Empty means the API fails
    # closed rather than accepting unauthenticated requests.
    SERVICE_AUTH_TOKEN: str = os.getenv("SERVICE_AUTH_TOKEN", "").strip()

    CORS_ORIGINS: List[str] = _env_list(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:3000,http://localhost:8080",
    )

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

    def validate(self) -> None:
        """Validate configuration at startup without revealing secret values.

        Development may omit the service token, in which case the API fails
        closed at request time. Production deployments must configure it.
        """

        allowed_environments = {"development", "test", "staging", "production"}
        if self.ENVIRONMENT not in allowed_environments:
            raise ValueError(
                "ENVIRONMENT must be one of: "
                + ", ".join(sorted(allowed_environments))
            )

        if not 1 <= self.PORT <= 65535:
            raise ValueError("PORT must be between 1 and 65535")
        if not isinstance(self.CORS_ORIGINS, list) or not self.CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS must contain at least one origin")

        if self.ENVIRONMENT == "production":
            problems = []
            if self.DEBUG:
                problems.append("DEBUG must be false in production")
            if not self.SERVICE_AUTH_TOKEN:
                problems.append("SERVICE_AUTH_TOKEN is required in production")
            elif len(self.SERVICE_AUTH_TOKEN) < 32:
                problems.append(
                    "SERVICE_AUTH_TOKEN must be at least 32 characters in production"
                )
            if any(origin.strip() == "*" for origin in self.CORS_ORIGINS):
                problems.append("wildcard CORS origins are not allowed in production")
            if any(
                not origin.startswith(("http://", "https://"))
                for origin in self.CORS_ORIGINS
            ):
                problems.append("CORS_ORIGINS entries must be absolute http(s) URLs")
            if problems:
                raise ValueError(
                    "Invalid production configuration: " + "; ".join(problems)
                )


settings = Settings()
