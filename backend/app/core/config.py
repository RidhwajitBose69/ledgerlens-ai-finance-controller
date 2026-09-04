import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DATABASE: str = "ledgerlens"

    LLM_PROVIDER: str = "mock"

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"

    RAZORPAY_ENABLED: bool = False
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    AUTO_RESOLUTION_THRESHOLD: float = 0.95
    MAX_AUTO_RESOLUTION_AMOUNT: int = 10000000  # 1,00,000 INR in paise

    SETTLEMENT_DATE_TOLERANCE_DAYS: int = 3

    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
