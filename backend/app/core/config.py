"""Application settings.

Responsible for loading configuration from environment variables (and the repo-root
`.env` file) into one typed `Settings` object, validated by pydantic-settings.
Required variables have no default, so the app fails fast at startup if they are
missing. Import the shared instance with `from app.core.config import settings`.
"""

from enum import StrEnum
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# repo root = backend/app/core/config.py -> parents[3]
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Env(StrEnum):
    DEV = "dev"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    # Required: no defaults on purpose.
    DATABASE_URL: str  # e.g. postgresql+asyncpg://demux:demux@localhost:5432/demux
    FRONTEND_URL: str  # allowed CORS origin, e.g. http://localhost:3000

    ENV: Env = Env.DEV
    LOG_LEVEL: str = "INFO"

    # Used by the test suite only (see tests/conftest.py).
    TEST_DATABASE_URL: str = "postgresql+asyncpg://demux:demux@localhost:5432/demux_test"

    # --- Auth (backend owns Google OAuth) ---
    BACKEND_URL: str = "http://localhost:8000"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    SECRET_KEY: str = ""  # signs the session cookie and OAuth state
    TOKEN_ENCRYPTION_KEY: str = ""  # Fernet key for Google tokens at rest
    SESSION_MAX_AGE_DAYS: int = 30

    # --- LLM (any OpenAI-compatible endpoint with tool calling) ---
    LLM_BASE_URL: str = "https://router.huggingface.co/v1"
    LLM_API_KEY: str = ""  # falls back to HF_TOKEN when empty
    HF_TOKEN: str = ""
    BUILD_MODEL: str = "zai-org/GLM-5.3:deepinfra"
    SYNC_MODEL: str = "zai-org/GLM-5.3:deepinfra"
    LLM_CALL_TIMEOUT_S: float = 180
    LLM_MAX_TOKENS: int = 16000
    LLM_TEMPERATURE: float = 0.2
    MAX_USD_PER_RUN: float = 3.0
    MAX_USD_PER_DAY: float = 15.0

    # --- Agent / flows ---
    SYNC_INTERVAL_MIN: int = 10
    LOOKBACK_DAYS: int = 90
    BUILD_MAX_THREADS: int = 150
    BATCH_THREADS: int = 8
    DATA_INLINE_MAX_CHARS: int = 120_000
    AGENT_DEBUG_TRANSCRIPTS: bool = False
    WORKER_CONCURRENCY: int = 3

    @property
    def llm_api_key(self) -> str:
        return self.LLM_API_KEY or self.HF_TOKEN

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.BACKEND_URL}/api/v1/auth/google/callback"


settings = Settings()  # type: ignore[call-arg]
