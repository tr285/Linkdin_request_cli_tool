"""
cache.py — Disk-based JSON cache with TTL.

Used by scrapers to avoid redundant LinkedIn requests within
a configurable time window (default: 24 hours).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from loguru import logger


class Cache:
    """Simple file-based JSON cache."""

    def __init__(self, cache_dir: str | Path = "cache", ttl_hours: int = 24) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def _key_path(self, key: str) -> Path:
        hashed = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{hashed}.json"

    def get(self, key: str) -> Any | None:
        """Return cached value or None if missing / expired."""
        path = self._key_path(key)
        if not path.exists():
            return None
        try:
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            stored_at = datetime.fromisoformat(data["stored_at"])
            if datetime.now(timezone.utc) - stored_at > self.ttl:
                logger.debug("Cache expired for key={}", key[:50])
                path.unlink(missing_ok=True)
                return None
            logger.debug("Cache hit for key={}", key[:50])
            return data["value"]
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Corrupt cache entry, deleting: {}", exc)
            path.unlink(missing_ok=True)
            return None

    def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        path = self._key_path(key)
        payload = {"stored_at": datetime.now(timezone.utc).isoformat(), "value": value}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Cache set for key={}", key[:50])

    def delete(self, key: str) -> None:
        self._key_path(key).unlink(missing_ok=True)

    def clear(self) -> int:
        """Remove all cache files. Returns number deleted."""
        count = 0
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
            count += 1
        logger.info("Cache cleared: {} files removed", count)
        return count

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        files = list(self.cache_dir.glob("*.json"))
        total_bytes = sum(f.stat().st_size for f in files)
        return {
            "entries": len(files),
            "total_size_kb": round(total_bytes / 1024, 1),
            "cache_dir": str(self.cache_dir.resolve()),
            "ttl_hours": self.ttl.total_seconds() / 3600,
        }
