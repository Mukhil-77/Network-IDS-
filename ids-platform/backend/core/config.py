"""
Application configuration.

Single source of truth for every environment-driven setting the API layer
needs. Reads from process environment variables first, falling back to a
`.env` file (see `.env.example`) if present - standard pydantic-settings
behavior. Nothing in backend/ml/ reads from here; that layer takes explicit
arguments (models_dir, version, etc.) so it stays framework-agnostic and
testable without an app context.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Where versioned model artifacts live - passed straight through to
    # backend.ml.predictor.get_predictor(models_dir=...).
    MODEL_PATH: str = "models"

    # Reported by GET / and GET /health, and used as the OpenAPI version.
    API_VERSION: str = "1.0.0"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    LOG_LEVEL: str = "INFO"

    # Comma-separated list of allowed CORS origins, or "*" for any origin.
    # Defaults permissive for local development; tighten in production via
    # the environment rather than editing code.
    CORS_ORIGINS: str = "*"

    # Placeholder toggle for the rate-limiting middleware (see
    # backend/core/middleware.py) - rate limiting itself is out of scope
    # for this milestone, but the switch is wired up so enabling it later
    # is a config change, not a code change.
    ENABLE_RATE_LIMIT: bool = False

    # Milestone 6: PostgreSQL connection string. Defaults to a local dev
    # Postgres instance; test fixtures (tests/database/conftest.py,
    # tests/api/conftest.py) override this with an in-memory SQLite URL so
    # the test suite needs no real database - see database/connection.py's
    # docstring for why the same models work against both.
    DATABASE_URL: str = "postgresql+psycopg2://ids_user:ids_password@localhost:5432/ids_platform"

    # --- Milestone 8: Response Engine ---------------------------------
    # Hard safety gate: even if a policy or an API caller requests
    # mode="live", live (potentially destructive) actions only actually run
    # if this is explicitly set to true. Left false, "live" silently falls
    # back to simulation with a logged warning - see response_engine's
    # simulation.py. This exists specifically so a misconfigured policy or
    # a stray API call can never take a destructive real-world action by
    # accident; enabling it is a deliberate, separate decision from turning
    # simulation_mode off in response_rules.yaml.
    ENABLE_LIVE_RESPONSE_ACTIONS: bool = False

    # Notification channels (optional - unset means that channel's actions
    # log what they *would* send and report success without an actual
    # network call, which is also what happens in simulation mode
    # regardless of these being set).
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    ALERT_EMAIL_FROM: str = ""
    ALERT_EMAIL_TO: str = ""

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    RESPONSE_WEBHOOK_URL: str = ""

    # --- Milestone 9: Authentication -----------------------------------
    # No safe default is shipped for a secret - generating one at import
    # time would silently invalidate every issued token on each restart,
    # which is confusing; instead auth/jwt_manager.py raises clearly at
    # startup if this is left as the placeholder in a way that matters
    # (see that module's docstring). Set a real value via JWT_SECRET_KEY.
    JWT_SECRET_KEY: str = "dev-only-insecure-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Seeded once at startup if no users exist yet (see auth/authentication.py's
    # seed_default_data()) - a working login out of the box for a fresh
    # deployment. Change this password immediately in any real deployment;
    # a startup log line says so loudly every time this default is used.
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
    DEFAULT_ADMIN_PASSWORD: str = "ChangeMe123!"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Cached Settings accessor. `lru_cache` means the .env file / environment
    is only read once per process; tests that need different settings
    should construct `Settings(...)` directly rather than relying on this
    cached singleton.
    """
    return Settings()
