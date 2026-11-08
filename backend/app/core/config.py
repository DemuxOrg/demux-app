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


settings = Settings()  # type: ignore[call-arg]
