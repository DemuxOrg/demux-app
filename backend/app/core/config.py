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

    # --- Gmail connection (backend owns Google OAuth; login is better-auth in the frontend) ---
    BACKEND_URL: str = "http://localhost:8000"
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    SECRET_KEY: str = ""  # signs the Gmail OAuth state
    TOKEN_ENCRYPTION_KEY: str = ""  # Fernet key for Google tokens at rest

    # --- LLM (any OpenAI-compatible endpoint with tool calling) ---
    LLM_BASE_URL: str = "https://router.huggingface.co/v1"
    LLM_API_KEY: str = ""  # falls back to HF_TOKEN when empty
    HF_TOKEN: str = ""
    # Defaults favour speed: a build should take about a minute.
    BUILD_MODEL: str = "Qwen/Qwen3.8-27B:nebius"
    SYNC_MODEL: str = "Qwen/Qwen3.8-27B:nebius"
    LLM_FALLBACK_MODEL: str = "Qwen/Qwen3.8-27B:nscale"  # used when the main one keeps failing
    LLM_REASONING_EFFORT: str = "none"  # "", none, low, medium, high (dropped if rejected)
    LLM_CALL_TIMEOUT_S: float = 60
    LLM_MAX_TOKENS: int = 8000
    LLM_TEMPERATURE: float = 0.2
    # The interface designer (docs/UI_GENERATION_PLAN.md §11): this model designs and
    # writes every workspace app (UX and code); the models above never write interface
    # code. Its answers are long, so it gets more tokens and time. The fallback is the same
    # model on another provider, so a build never quietly falls back to a weaker designer.
    # Together serves GLM-5.2 at a steady ~365-390 tok/s; CoreWeave varied 225-335 (both
    # measured 2026-11-27). Together costs more ($1.40/$4.40 vs $0.62/$2.42 per M).
    UI_MODEL: str = "zai-org/GLM-5.2:together"
    UI_FALLBACK_MODEL: str = "zai-org/GLM-5.2:coreweave"
    # GLM reasons before it writes (~19k tokens seen): 24k cut apps off mid-code and the
    # retry cost minutes.
    UI_MAX_TOKENS: int = 40000
    UI_CALL_TIMEOUT_S: float = 300
    UI_TEMPERATURE: float = 0.7
    # "none": GLM writes the app without hidden reasoning (~20k tokens fewer, about twice
    # as fast). On Together "low" reasons as much as the default. Set "" to restore it.
    UI_REASONING_EFFORT: str = "none"
    UI_MAX_ATTEMPTS: int = 3  # first design + fixes after failed app checks
    MAX_USD_PER_RUN: float = 3.0
    MAX_USD_PER_DAY: float = 15.0

    # --- Agent / flows ---
    SYNC_INTERVAL_MIN: int = 10
    LOOKBACK_DAYS: int = 90
    BUILD_MAX_THREADS: int = 80
    # How long a build waits for the user's setup answers (questions, layouts), seconds.
    SETUP_WAIT_SECONDS: int = 120
    BATCH_THREADS: int = 6
    BATCH_MAX_CHARS: int = 45_000  # a batch is also cut when its email text gets this big
    PROCESS_CONCURRENCY: int = 8  # build backfill batches run in parallel
    DATA_INLINE_MAX_CHARS: int = 120_000
    AGENT_DEBUG_TRANSCRIPTS: bool = False
    WORKER_CONCURRENCY: int = 3
    # Dev only (ENV=dev): the worker reads this fake mailbox JSON instead of Gmail.
    DEV_FAKE_MAILBOX: str = ""

    # --- Admin (/admin) ---
    # Comma-separated login emails that may open /admin (users.is_admin also grants it).
    ADMIN_EMAILS: str = ""
    # Demo inbox: a test Gmail that /admin fills with synthetic threads over IMAP, using an
    # app password (Google account > Security > App passwords; needs 2-Step Verification).
    TEST_GMAIL: str = ""
    TEST_GMAIL_PASSWORD: str = ""
    DEMO_IMAP_HOST: str = "imap.gmail.com"
    DEMO_MODEL: str = ""  # empty: BUILD_MODEL (a Qwen model on the Hugging Face router)

    # --- Access (who may sign up and use Demux; app/services/access.py) ---
    # Stripe account the landing page bills with. A restricted key with read access to
    # Customers and Subscriptions is enough. Empty: no Stripe lookups (grants and admins
    # still work).
    STRIPE_SECRET_KEY: str = ""
    # Signing secret of this API's own webhook endpoint in Stripe
    # (<BACKEND_URL>/api/v1/billing/stripe/webhook), not the landing page's.
    STRIPE_WEBHOOK_SECRET: str = ""
    # Shared with the frontend server: it asks /internal/signup-check before better-auth
    # creates an account. Generated by `make setup` / `make up` when empty.
    INTERNAL_API_SECRET: str = ""
    # The marketing site, where people subscribe (links on the "no access" screen).
    LANDING_URL: str = "https://www.usedemux.com"

    @property
    def admin_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.ADMIN_EMAILS.split(",") if e.strip()}

    @property
    def demo_inbox_configured(self) -> bool:
        return bool(self.TEST_GMAIL and self.TEST_GMAIL_PASSWORD)

    @property
    def llm_api_key(self) -> str:
        return self.LLM_API_KEY or self.HF_TOKEN

    @property
    def uses_fake_mailbox(self) -> bool:
        return bool(self.DEV_FAKE_MAILBOX) and self.ENV == Env.DEV

    @property
    def google_redirect_uri(self) -> str:
        return f"{self.BACKEND_URL}/api/v1/auth/google/callback"


settings = Settings()  # type: ignore[call-arg]
