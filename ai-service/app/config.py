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
