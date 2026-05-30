import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "LLM Inference Logging & Ingestion System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Database Settings
    # Default to local SQLite database if Postgres is not configured
    DATABASE_URL: str = "sqlite:///./app.db"
    
    # Gemini API Key
    GEMINI_API_KEY: str = ""
    
    # Ingestion pipeline settings
    INGEST_URL: str = "http://localhost:8000/api/logs/ingest"
    
    # Redactor settings
    REDACT_PII: bool = True

    # Redis settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
