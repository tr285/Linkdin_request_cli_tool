"""
settings.py — Runtime user settings backed by SQLite.

Wraps the database settings table to provide typed get/set
operations with schema validation.
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from linkedin_ai.database import Database

# All known settings keys with their types and descriptions
SETTINGS_SCHEMA: dict[str, dict[str, Any]] = {
    "openai_model": {
        "type": str,
        "default": "gpt-4o-mini",
        "description": "OpenAI model to use for AI features",
        "choices": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    },
    "theme": {
        "type": str,
        "default": "dark",
        "description": "CLI colour theme",
        "choices": ["dark", "light"],
    },
    "headless": {
        "type": bool,
        "default": False,
        "description": "Run browser in headless mode",
        "choices": ["true", "false"],
    },
    "rate_limit_delay": {
        "type": float,
        "default": 3.0,
        "description": "Seconds to wait between LinkedIn requests",
    },
    "max_search_results": {
        "type": int,
        "default": 50,
        "description": "Maximum profiles to fetch per search",
    },
    "cache_ttl_hours": {
        "type": int,
        "default": 24,
        "description": "Cache time-to-live in hours",
    },
    "export_dir": {
        "type": str,
        "default": "reports",
        "description": "Directory for exported reports",
    },
}


class Settings:
    """Runtime settings manager backed by SQLite."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def get(self, key: str) -> Any:
        schema = SETTINGS_SCHEMA.get(key)
        default = schema["default"] if schema else None
        raw = self._db.get_setting(key, str(default) if default is not None else "")
        if raw == "" and schema:
            return schema["default"]
        if schema:
            cast = schema["type"]
            if cast is bool:
                return raw.lower() in ("true", "1", "yes")
            try:
                return cast(raw)
            except (ValueError, TypeError):
                return schema["default"]
        return raw

    def set(self, key: str, value: Any) -> None:
        if key not in SETTINGS_SCHEMA:
            logger.warning("Unknown setting key: {}", key)
        self._db.set_setting(key, str(value))
        logger.info("Setting updated: {}={}", key, value)

    def list_all(self) -> list[dict[str, Any]]:
        db_values = self._db.list_settings()
        result = []
        for key, schema in SETTINGS_SCHEMA.items():
            result.append({
                "key": key,
                "value": db_values.get(key, str(schema["default"])),
                "default": str(schema["default"]),
                "description": schema["description"],
                "choices": ", ".join(schema.get("choices", [])) or "—",
            })
        return result

    def reset(self, key: str) -> None:
        schema = SETTINGS_SCHEMA.get(key)
        if schema:
            self.set(key, schema["default"])
            logger.info("Setting reset to default: {}={}", key, schema["default"])
