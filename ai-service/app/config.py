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

settings = Settings()
