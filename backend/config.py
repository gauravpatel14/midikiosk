"""Configuration and environment variables for MediKiosk backend."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from backend/ or project root if present
load_dotenv()
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    # Service Environment
    ENV: str = os.getenv("ENV", "development")
    APP_NAME: str = "MediKiosk Clinical History Backend"
    
    # Internal JWT Authentication (Kiosk to Backend)
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "medikiosk_internal_secret_key_change_in_production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRY_MINUTES: int = int(os.getenv("JWT_EXPIRY_MINUTES", "1440"))  # 24 hours
    KIOSK_SHARED_SECRET: str = os.getenv("KIOSK_SHARED_SECRET", "kiosk_hospital_aiia_secret_2026")

    # ABDM (Ayushman Bharat Digital Mission) Sandbox Config
    ABDM_CLIENT_ID: str = os.getenv("ABDM_CLIENT_ID", "")
    ABDM_CLIENT_SECRET: str = os.getenv("ABDM_CLIENT_SECRET", "")
    ABDM_GATEWAY_URL: str = os.getenv("ABDM_GATEWAY_URL", "https://dev.abdm.gov.in/gateway/v0.5")
    ABDM_ABHA_URL: str = os.getenv("ABDM_ABHA_URL", "https://abhasbx.abdm.gov.in/abha/api/v3")
    ABDM_HIP_ID: str = os.getenv("ABDM_HIP_ID", "IN0510000123")  # Hospital HIP ID

    # OpenAI Configuration (Never hardcoded in source - loaded strictly from .env / env vars)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@localhost:5432/medikiosk_db",
    )


settings = Settings()
