"""Centralised, validated configuration for the MediKiosk backend.

Every external credential, endpoint, model path and feature toggle is read from
the environment (``.env`` file or real process environment). Nothing is
hardcoded, and production deployments are validated at start-up so a
mis-configured hospital server fails fast instead of silently degrading.

Design notes
------------
* ``pydantic-settings`` gives typed parsing plus ``.env`` support.
* ``ENV`` drives *behavioural* strictness:
    - ``development`` / ``test``  -> permissive, offline-friendly defaults.
    - ``staging`` / ``production`` -> secrets must be supplied, insecure
      defaults are rejected by :meth:`Settings.validate_runtime`.
* ``ABDM_ENVIRONMENT`` (``sandbox`` | ``production``) selects the ABDM base
  URLs so the *same* code path talks to the sandbox or the live gateway.
* ``OFFLINE_MODE`` forces every AI subsystem onto locally hosted models, which
  is the DPDP-safe default for facilities without an approved egress path.
"""

from __future__ import annotations

import functools
import logging
import os
import secrets
from pathlib import Path
from typing import Any, List, Literal, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

# ---------------------------------------------------------------------------
# ABDM endpoint matrix (official documented hosts)
# ---------------------------------------------------------------------------
ABDM_ENDPOINTS: dict[str, dict[str, str]] = {
    "sandbox": {
        "gateway": "https://dev.abdm.gov.in/gateway",
        "abha": "https://abhasbx.abdm.gov.in/abha/api",
        "phr": "https://phrsbx.abdm.gov.in",
        "hprid": "https://hpridsbx.abdm.gov.in",
        "facility": "https://facilitysbx.abdm.gov.in",
    },
    "production": {
        "gateway": "https://live.abdm.gov.in/gateway",
        "abha": "https://abha.abdm.gov.in/abha/api",
        "phr": "https://phr.abdm.gov.in",
        "hprid": "https://hprid.abdm.gov.in",
        "facility": "https://facility.abdm.gov.in",
    },
}

INSECURE_PLACEHOLDERS = {
    "",
    "change_me",
    "changeme",
    "medikiosk_internal_secret_key_change_in_production",
    "kiosk_hospital_aiia_secret_2026",
    "generate_a_random_32_byte_secret_for_production",
    "your_openai_api_key_here",
    "your_abdm_client_id",
    "your_abdm_client_secret",
}


class Settings(BaseSettings):
    """Typed application settings loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    ENV: Literal["development", "test", "staging", "production"] = "development"
    APP_NAME: str = "MediKiosk Clinical History Backend"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    API_PREFIX: str = ""
    CORS_ORIGINS: str = "*"
    TRUSTED_HOSTS: str = "*"
    ENABLE_DOCS: bool = True

    #: When true every AI subsystem (ASR/TTS/OCR/NER/LLM) uses only locally
    #: hosted models. No patient data leaves the hospital network.
    OFFLINE_MODE: bool = False

    HOSPITAL_NAME: str = "All India Institute of Ayurveda - Clinical OPD"
    HOSPITAL_FACILITY_ID: str = "IN0510000123"
    HOSPITAL_STATE: str = "Delhi"

    # ------------------------------------------------------------------
    # Security / cryptography
    # ------------------------------------------------------------------
    JWT_SECRET_KEY: str = "medikiosk_internal_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "medikiosk-internal-auth"
    JWT_AUDIENCE: str = "medikiosk-api"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    KIOSK_TOKEN_EXPIRE_MINUTES: int = 720

    KIOSK_SHARED_SECRET: str = "kiosk_hospital_aiia_secret_2026"

    #: Fernet key (44-char urlsafe base64) used for application-level
    #: encryption of PII columns. Generate with
    #: ``python -c "from cryptography.fernet import Fernet;
    #: print(Fernet.generate_key().decode())"``.
    FIELD_ENCRYPTION_KEY: str = ""
    #: Previous keys, comma separated, kept for transparent decryption during
    #: key rotation.
    FIELD_ENCRYPTION_KEY_PREVIOUS: str = ""
    #: Dedicated pepper for Aadhaar tokenisation (never reuse the JWT secret).
    AADHAAR_HASH_PEPPER: str = ""

    PASSWORD_MIN_LENGTH: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    RATE_LIMIT_PER_MINUTE: int = 240

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/medikiosk_db"
    #: Optional explicit sync URL (Alembic / management scripts). Derived from
    #: :attr:`DATABASE_URL` when omitted.
    DATABASE_SYNC_URL: str = ""
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_STATEMENT_TIMEOUT_MS: int = 30_000
    SQL_ECHO: bool = False

    # ------------------------------------------------------------------
    # Redis cache / queue
    # ------------------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600
    CACHE_NAMESPACE: str = "medikiosk"

    # ------------------------------------------------------------------
    # ABDM / ABHA
    # ------------------------------------------------------------------
    ABDM_ENVIRONMENT: Literal["sandbox", "production"] = "sandbox"
    ABDM_ENABLED: bool = True
    ABDM_CLIENT_ID: str = ""
    ABDM_CLIENT_SECRET: str = ""
    ABDM_HIP_ID: str = "IN0510000123"
    ABDM_HIP_NAME: str = "All India Institute of Ayurveda"
    ABDM_CM_ID: str = "sbx"
    #: Overrides for air-gapped or proxied deployments.
    ABDM_GATEWAY_URL: str = ""
    ABDM_ABHA_URL: str = ""
    ABDM_PHR_URL: str = ""
    #: ABDM publishes an RSA public key used to encrypt Aadhaar/OTP payloads.
    ABDM_PUBLIC_KEY_PEM: str = ""
    ABDM_PUBLIC_KEY_URL: str = ""
    ABDM_REQUEST_TIMEOUT: float = 15.0
    ABDM_MAX_RETRIES: int = 3
    ABDM_WEBHOOK_SECRET: str = ""
    ABDM_TOKEN_LEEWAY_SECONDS: int = 60
    ABDM_REVOCATION_RETRY_ENABLED: bool = True
    ABDM_REVOCATION_RETRY_INTERVAL_SECONDS: int = 300

    # ------------------------------------------------------------------
    # Speech (ASR / TTS)
    # ------------------------------------------------------------------
    SPEECH_PROVIDER: Literal["auto", "bhashini", "offline"] = "auto"
    SPEECH_CONFIG_PATH: str = ""
    SUPPORTED_LANGUAGES: str = "hi,en,ta,bn,mr,te"
    DEFAULT_LANGUAGE: str = "hi"

    BHASHINI_ENABLED: bool = True
    BHASHINI_USER_ID: str = ""
    BHASHINI_API_KEY: str = ""
    BHASHINI_INFERENCE_API_KEY: str = ""
    BHASHINI_PIPELINE_ID: str = "64392f96daac500b55c543cd"
    BHASHINI_CONFIG_URL: str = (
        "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
    )
    BHASHINI_INFERENCE_URL: str = (
        "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
    )
    BHASHINI_TIMEOUT: float = 20.0

    VOSK_MODELS_DIR: str = "/opt/medikiosk/models/vosk"
    PIPER_MODELS_DIR: str = "/opt/medikiosk/models/piper"
    PIPER_BINARY: str = "piper"
    ESPEAK_BINARY: str = "espeak-ng"
    AUDIO_WORK_DIR: str = "/var/lib/medikiosk/audio"
    ASR_SAMPLE_RATE: int = 16_000
    SPEECH_MAX_WORKERS: int = 4

    # ------------------------------------------------------------------
    # OCR
    # ------------------------------------------------------------------
    OCR_ENGINE: Literal["auto", "paddleocr", "easyocr", "tesseract"] = "auto"
    OCR_LANGUAGES: str = "eng,hin"
    TESSERACT_PATH: str = ""
    TESSDATA_PREFIX: str = ""
    OCR_MIN_CONFIDENCE: float = 0.60
    OCR_REVIEW_THRESHOLD: float = 0.75
    OCR_DPI: int = 300
    OCR_MAX_PAGES: int = 20
    OCR_MAX_FILE_MB: int = 25
    OCR_WORK_DIR: str = "/var/lib/medikiosk/documents"
    OCR_MAX_WORKERS: int = 2
    PADDLEOCR_USE_GPU: bool = False
    PADDLEOCR_MODEL_DIR: str = ""

    HANDWRITING_ENGINE: Literal["auto", "trocr", "document_ai", "none"] = "auto"
    TROCR_MODEL_PATH: str = ""
    GOOGLE_DOCUMENT_AI_ENABLED: bool = False
    GOOGLE_DOCUMENT_AI_PROJECT: str = ""
    GOOGLE_DOCUMENT_AI_LOCATION: str = "us"
    GOOGLE_DOCUMENT_AI_PROCESSOR_ID: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = ""

    # ------------------------------------------------------------------
    # Clinical NLP
    # ------------------------------------------------------------------
    NER_ENABLED: bool = True
    SCISPACY_DISEASE_MODEL: str = "en_ner_bc5cdr_md"
    SCISPACY_BIONLP_MODEL: str = "en_ner_bionlp13cg_md"
    MED7_MODEL: str = "en_core_med7_lg"
    SPACY_BASE_MODEL: str = "en_core_web_sm"
    NER_PRELOAD_ON_STARTUP: bool = True

    # Local LLM (Ollama) — preferred, keeps data on premises
    OLLAMA_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b-instruct-q4_K_M"
    OLLAMA_TIMEOUT: float = 60.0
    OLLAMA_NUM_CTX: int = 8192

    # Cloud LLM — disabled by default (DPDP data residency)
    OPENAI_ENABLED: bool = False
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT: float = 30.0

    # ------------------------------------------------------------------
    # Dialogue engine
    # ------------------------------------------------------------------
    DIALOGUE_MAX_QUESTIONS: int = 40
    DIALOGUE_SESSION_TIMEOUT_MINUTES: int = 30
    DIALOGUE_LLM_QUESTIONS: bool = True
    TERMINOLOGY_DIR: str = ""

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    SUMMARY_LLM_NARRATIVE: bool = True
    SUMMARY_MAX_WORDS: int = 500

    # ------------------------------------------------------------------
    # HIS integration
    # ------------------------------------------------------------------
    HIS_CONFIG_PATH: str = ""
    HIS_ADAPTER: Literal["fhir", "hl7v2", "webhook", "file_drop", "mock"] = "mock"
    HIS_FHIR_BASE_URL: str = ""
    HIS_FHIR_TOKEN: str = ""
    HIS_FHIR_CLIENT_ID: str = ""
    HIS_FHIR_CLIENT_SECRET: str = ""
    HIS_FHIR_TOKEN_URL: str = ""
    HIS_MLLP_HOST: str = "127.0.0.1"
    HIS_MLLP_PORT: int = 2575
    HIS_MLLP_TIMEOUT: float = 10.0
    HIS_MLLP_TLS: bool = False
    HIS_WEBHOOK_URL: str = ""
    HIS_WEBHOOK_SECRET: str = ""
    HIS_FILE_DROP_DIR: str = "/var/spool/medikiosk/his-outbound"
    HIS_SENDING_APP: str = "MEDIKIOSK"
    HIS_SENDING_FACILITY: str = "AIIA_OPD"
    HIS_RECEIVING_APP: str = "HOSPITAL_HIS"
    HIS_RECEIVING_FACILITY: str = "CENTRAL_HOSPITAL"
    HIS_MAX_RETRIES: int = 3
    HIS_TIMEOUT: float = 15.0

    # ------------------------------------------------------------------
    # Triage notifications
    # ------------------------------------------------------------------
    TRIAGE_WEBHOOK_URL: str = ""
    TRIAGE_SMS_ENABLED: bool = False
    TRIAGE_SMS_GATEWAY_URL: str = ""
    TRIAGE_SMS_API_KEY: str = ""
    TRIAGE_SMS_SENDER_ID: str = "AIIAMK"
    TRIAGE_SMS_RECIPIENTS: str = ""

    # ------------------------------------------------------------------
    # Retention & Archival (DPDP Act 2023)
    # ------------------------------------------------------------------
    RAW_MEDIA_RETENTION_HOURS: int = 24
    AUDIT_LOG_RETENTION_DAYS: int = 2555  # 7 years
    ABANDONED_SESSION_PURGE_HOURS: int = 24
    RETENTION_SWEEP_INTERVAL_MINUTES: int = 60
    OUTBOX_RETRY_INTERVAL_SECONDS: int = 60
    DOCUMENT_RETENTION_MODE: Literal["delete", "archive_local", "archive_s3"] = "archive_local"
    ARCHIVE_LOCAL_PATH: str = "/tmp/medikiosk_archive"
    S3_BUCKET_NAME: str = "medikiosk-records"
    AWS_REGION: str = "ap-south-1"

    # ------------------------------------------------------------------
    # Clinical Safety & Knowledge Bases
    # ------------------------------------------------------------------
    DRUG_INTERACTION_SOURCE: Literal["rxnav", "openfda", "custom_csv"] = "custom_csv"
    DRUG_INTERACTION_DATA_PATH: str = "backend/data/drug_interactions.csv"
    AYUSH_SAFETY_DATA_PATH: str = "backend/data/ayush_safety.json"
    MIN_DRUG_INTERACTIONS: int = 1000
    MIN_AYUSH_FORMULATIONS: int = 20

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------
    @field_validator("LOG_LEVEL")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}:
            raise ValueError(f"Invalid LOG_LEVEL: {value}")
        return level

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_async_dsn(cls, value: str) -> str:
        """Force an async driver for the primary application engine."""
        value = value.strip()
        if not value:
            raise ValueError("DATABASE_URL must not be empty")
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql+psycopg2://"):
            return value.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("sqlite://") and "+aiosqlite" not in value:
            return value.replace("sqlite://", "sqlite+aiosqlite://", 1)
        return value

    @model_validator(mode="after")
    def _fill_derived(self) -> "Settings":
        endpoints = ABDM_ENDPOINTS[self.ABDM_ENVIRONMENT]
        if not self.ABDM_GATEWAY_URL:
            self.ABDM_GATEWAY_URL = endpoints["gateway"]
        if not self.ABDM_ABHA_URL:
            self.ABDM_ABHA_URL = endpoints["abha"]
        if not self.ABDM_PHR_URL:
            self.ABDM_PHR_URL = endpoints["phr"]
        if not self.ABDM_PUBLIC_KEY_URL:
            self.ABDM_PUBLIC_KEY_URL = f"{endpoints['abha']}/v3/profile/public/certificate"
        if self.ABDM_ENVIRONMENT == "production" and self.ABDM_CM_ID == "sbx":
            self.ABDM_CM_ID = "abdm"

        if not self.DATABASE_SYNC_URL:
            self.DATABASE_SYNC_URL = (
                self.DATABASE_URL.replace("+asyncpg", "+psycopg2").replace(
                    "+aiosqlite", ""
                )
            )
        if not self.AADHAAR_HASH_PEPPER:
            # Deterministic derivation so existing tokens stay resolvable when
            # an operator has not yet provisioned a dedicated pepper.
            self.AADHAAR_HASH_PEPPER = f"aadhaar-token::{self.JWT_SECRET_KEY}"
        if not self.SPEECH_CONFIG_PATH:
            self.SPEECH_CONFIG_PATH = str(BACKEND_DIR / "speech_config.json")
        if not self.HIS_CONFIG_PATH:
            self.HIS_CONFIG_PATH = str(BACKEND_DIR / "his_config.json")
        if not self.TERMINOLOGY_DIR:
            self.TERMINOLOGY_DIR = str(BACKEND_DIR / "data")
        if self.OFFLINE_MODE:
            self.OPENAI_ENABLED = False
            self.BHASHINI_ENABLED = False
            self.ABDM_ENABLED = False
            self.GOOGLE_DOCUMENT_AI_ENABLED = False
        return self

    # -- convenience accessors ------------------------------------------
    @property
    def is_production(self) -> bool:
        return self.ENV in {"production", "staging"}

    @property
    def is_testing(self) -> bool:
        return self.ENV == "test"

    @property
    def supported_languages(self) -> List[str]:
        return [x.strip().lower() for x in self.SUPPORTED_LANGUAGES.split(",") if x.strip()]

    @property
    def ocr_language_list(self) -> List[str]:
        return [x.strip().lower() for x in self.OCR_LANGUAGES.split(",") if x.strip()]

    @property
    def cors_origin_list(self) -> List[str]:
        raw = self.CORS_ORIGINS.strip()
        if raw in {"*", ""}:
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def trusted_host_list(self) -> List[str]:
        raw = self.TRUSTED_HOSTS.strip()
        if raw in {"*", ""}:
            return ["*"]
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def triage_sms_recipient_list(self) -> List[str]:
        return [x.strip() for x in self.TRIAGE_SMS_RECIPIENTS.split(",") if x.strip()]

    @property
    def abdm_configured(self) -> bool:
        return bool(
            self.ABDM_ENABLED
            and self.ABDM_CLIENT_ID
            and self.ABDM_CLIENT_SECRET
            and self.ABDM_CLIENT_ID not in INSECURE_PLACEHOLDERS
            and self.ABDM_CLIENT_SECRET not in INSECURE_PLACEHOLDERS
        )

    @property
    def bhashini_configured(self) -> bool:
        return bool(
            self.BHASHINI_ENABLED
            and self.BHASHINI_USER_ID
            and self.BHASHINI_API_KEY
            and not self.BHASHINI_API_KEY.startswith("mock_")
        )

    @property
    def openai_configured(self) -> bool:
        return bool(
            self.OPENAI_ENABLED
            and self.OPENAI_API_KEY
            and self.OPENAI_API_KEY not in INSECURE_PLACEHOLDERS
        )

    # -- runtime validation ---------------------------------------------
    def validate_runtime(self) -> List[str]:
        """Return a list of fatal misconfigurations for the current ``ENV``.

        In development the caller logs the problems as warnings; in
        staging/production the application refuses to boot.
        """
        problems: List[str] = []

        if self.JWT_SECRET_KEY in INSECURE_PLACEHOLDERS or len(self.JWT_SECRET_KEY) < 32:
            problems.append(
                "JWT_SECRET_KEY must be a unique random value of at least 32 characters"
            )
        if self.KIOSK_SHARED_SECRET in INSECURE_PLACEHOLDERS or len(self.KIOSK_SHARED_SECRET) < 24:
            problems.append(
                "KIOSK_SHARED_SECRET must be a unique random value of at least 24 characters"
            )
        if not self.FIELD_ENCRYPTION_KEY:
            problems.append(
                "FIELD_ENCRYPTION_KEY is required so patient PII is encrypted at rest"
            )
        if self.ABDM_ENABLED and not self.abdm_configured:
            problems.append(
                "ABDM_ENABLED is true but ABDM_CLIENT_ID / ABDM_CLIENT_SECRET are missing"
            )
        if self.DATABASE_URL.startswith("sqlite"):
            problems.append("SQLite is not supported in production; use PostgreSQL")
        if self.ENABLE_DOCS and self.ENV == "production":
            problems.append(
                "ENABLE_DOCS should be false in production to avoid exposing the API schema"
            )
        if self.cors_origin_list == ["*"]:
            problems.append("CORS_ORIGINS must list explicit kiosk/HIS origins in production")
        if self.HIS_ADAPTER == "mock":
            problems.append("HIS_ADAPTER is 'mock'; configure a real hospital adapter")
        if not self.OFFLINE_MODE and self.OPENAI_ENABLED and not self.openai_configured:
            problems.append("OPENAI_ENABLED is true but OPENAI_API_KEY is missing")
        return problems

    def describe(self) -> dict[str, Any]:
        """Non-secret configuration snapshot for ``/health/config`` and logs."""
        return {
            "env": self.ENV,
            "version": self.APP_VERSION,
            "offline_mode": self.OFFLINE_MODE,
            "database": self.DATABASE_URL.split("@")[-1],
            "redis_enabled": self.REDIS_ENABLED,
            "abdm_environment": self.ABDM_ENVIRONMENT,
            "abdm_configured": self.abdm_configured,
            "speech_provider": self.SPEECH_PROVIDER,
            "bhashini_configured": self.bhashini_configured,
            "ocr_engine": self.OCR_ENGINE,
            "ner_enabled": self.NER_ENABLED,
            "ollama_enabled": self.OLLAMA_ENABLED,
            "openai_configured": self.openai_configured,
            "his_adapter": self.HIS_ADAPTER,
            "languages": self.supported_languages,
        }


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (safe as a FastAPI dependency)."""
    instance = Settings()
    if instance.is_testing and not instance.FIELD_ENCRYPTION_KEY:
        # Deterministic ephemeral key so tests can exercise encryption paths.
        from cryptography.fernet import Fernet

        object.__setattr__(instance, "FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    return instance


def generate_secret(length: int = 48) -> str:
    """Helper used by ``scripts/generate_secrets.py`` and operator docs."""
    return secrets.token_urlsafe(length)


settings = get_settings()

# ``TESSDATA_PREFIX`` must be exported before pytesseract/PaddleOCR import.
if settings.TESSDATA_PREFIX:
    os.environ.setdefault("TESSDATA_PREFIX", settings.TESSDATA_PREFIX)
if settings.GOOGLE_APPLICATION_CREDENTIALS:
    os.environ.setdefault(
        "GOOGLE_APPLICATION_CREDENTIALS", settings.GOOGLE_APPLICATION_CREDENTIALS
    )
