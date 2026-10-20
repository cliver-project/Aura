"""Application settings.

Precedence is environment > .env > database overrides > defaults. The database
layer is applied by SettingsService; this module owns the environment-backed
baseline every other layer is merged over.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AURA_",
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Aura"
    database_url: str = "postgresql+asyncpg://aura:aura@127.0.0.1:5433/aura"

    gitea_url: str = "http://localhost:3000"
    gitea_user: str = "aura"
    gitea_password: str = ""
    gitea_token: str = ""
    gitea_owner: str = "aura"
    gitea_request_timeout: float = 30.0
    gitea_language: str = "en-US"

    workspace_dir: Path = Field(default=REPO_ROOT / "var" / "workspaces")
    log_dir: Path = Field(default=REPO_ROOT / "var" / "logs")
    skills_dir: Path = Field(default=REPO_ROOT / "skills")

    claude_bin: str = "claude"
    default_model: str = ""
    permission_mode: str = "bypassPermissions"
    max_budget_usd: float = 10.0
    max_concurrent_runs: int = 3
    agent_timeout_seconds: int = 3600
    public_url: str = "http://127.0.0.1:5173"
    database_admin_url: str = "http://127.0.0.1:8081"

    anthropic_base_url: str = ""
    anthropic_auth_token: str = ""
    anthropic_model: str = ""
    anthropic_default_opus_model: str = ""
    anthropic_default_sonnet_model: str = ""
    anthropic_default_haiku_model: str = ""
    claude_code_subagent_model: str = ""
    claude_code_effort_level: str = ""
    claude_code_auto_compact_window: str = ""
    claude_code_disable_unknown_model_window_enforcement: bool = False
    model_prices: dict[str, dict[str, float]] = {}

    ragflow_url: str = ""
    ragflow_api_key: str = ""
    ragflow_account_email: str = ""
    # Empty means: use AURA_GITEA_PASSWORD, then the local "aura" fallback.
    ragflow_account_password: str = ""
    ragflow_mcp_url: str = "http://127.0.0.1:9382/sse"
    ragflow_language: str = "en"
    ragflow_web_url: str = "http://127.0.0.1:8080"

    default_locale: str = "en"
    default_theme: str = "system"
    auto_pipeline: bool = True

    cors_origins: list[str] = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]

    @property
    def sync_database_url(self) -> str:
        """The same database URL with the synchronous psycopg driver.

        Alembic uses this URL; the application keeps asyncpg. The password is
        rendered explicitly because SQLAlchemy masks it by default.
        """
        url = make_url(self.database_url)
        if url.get_backend_name() != "postgresql":
            return url.render_as_string(hide_password=False)
        return url.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)

    @property
    def gitea_owner_name(self) -> str:
        return self.gitea_owner or self.gitea_user

    @property
    def gitea_web_url(self) -> str:
        return self.gitea_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
