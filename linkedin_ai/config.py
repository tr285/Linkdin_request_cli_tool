"""
config.py — Application configuration via Pydantic Settings.

Reads from environment variables and a .env file. All settings
have sensible defaults so the app works out-of-the-box.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Central application configuration.

    Values are resolved in this priority order:
    1. Environment variables
    2. .env file (searched from CWD upward)
    3. Default values below
    """

    model_config = SettingsConfigDict(
        env_prefix="LIAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=2048, alias="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.7, alias="OPENAI_TEMPERATURE")

    # ── App behaviour ────────────────────────────────────────────────────────
    theme: Literal["dark", "light"] = Field(default="dark")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    headless: bool = Field(default=False)
    rate_limit_delay: float = Field(default=3.0)  # seconds between LinkedIn requests

    # ── Paths ────────────────────────────────────────────────────────────────
    database_path: Path = Field(default=Path("database/liai.db"))
    cache_dir: Path = Field(default=Path("cache"))
    export_dir: Path = Field(default=Path("reports"))
    log_dir: Path = Field(default=Path("logs"))
    cookies_path: Path = Field(default=Path(".liai_session.json"))

    # ── Scraping limits ──────────────────────────────────────────────────────
    max_search_results: int = Field(default=50)
    max_profile_posts: int = Field(default=10)
    cache_ttl_hours: int = Field(default=24)

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def _coerce_empty_key(cls, v: object) -> str:
        return str(v) if v else ""

    @field_validator("openai_temperature")
    @classmethod
    def _validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 2.0:
            raise ValueError("openai_temperature must be between 0.0 and 2.0")
        return v

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key) and self.openai_api_key.startswith("sk-")

    def ensure_dirs(self) -> None:
        """Create all required directories if they don't exist."""
        for d in (self.database_path.parent, self.cache_dir, self.export_dir, self.log_dir):
            d.mkdir(parents=True, exist_ok=True)


# Module-level singleton — lazily instantiated
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Return the application config singleton."""
    global _config
    if _config is None:
        _config = AppConfig()
    return _config


def reset_config() -> None:
    """Force re-read of config (useful in tests)."""
    global _config
    _config = None
