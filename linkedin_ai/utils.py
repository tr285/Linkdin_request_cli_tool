"""
utils.py — Shared utility helpers.

Includes: retry decorator, text helpers, slug generation, date formatting,
character-limit enforcement, and pretty table builders.
"""

from __future__ import annotations

import functools
import re
import time
import unicodedata
from datetime import datetime, timezone
from typing import Any, Callable, TypeVar

from loguru import logger
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

F = TypeVar("F", bound=Callable[..., Any])


# ── Retry decorator ───────────────────────────────────────────────────────────

def with_retry(
    max_attempts: int = 3,
    wait_min: float = 1.0,
    wait_max: float = 10.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries a function with exponential backoff."""
    def decorator(func: F) -> F:
        @retry(
            retry=retry_if_exception_type(exceptions),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=wait_min, max=wait_max),
            reraise=True,
        )
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        return wrapper  # type: ignore[return-value]
    return decorator


# ── Text helpers ──────────────────────────────────────────────────────────────

def truncate(text: str, max_len: int, suffix: str = "…") -> str:
    """Truncate text to max_len characters, appending suffix if cut."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def enforce_char_limit(text: str, limit: int = 300) -> str:
    """Enforce LinkedIn connection-note character limit (300 chars)."""
    return truncate(text, limit)


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-_")


def clean_text(text: str) -> str:
    """Strip excessive whitespace and normalise line endings."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r" {2,}", " ", text).strip()


def extract_linkedin_id(url: str) -> str:
    """Extract the LinkedIn profile ID / slug from a URL."""
    match = re.search(r"linkedin\.com/in/([^/?#]+)", url)
    return match.group(1) if match else ""


def now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def format_date(dt: datetime | str | None) -> str:
    """Format a datetime to a human-readable string."""
    if dt is None:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return dt
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def parse_number(text: str) -> int:
    """Parse '1,234' or '12K' style numbers to int."""
    text = text.strip().upper().replace(",", "")
    if text.endswith("K"):
        return int(float(text[:-1]) * 1_000)
    if text.endswith("M"):
        return int(float(text[:-1]) * 1_000_000)
    try:
        return int(text)
    except ValueError:
        return 0


# ── Rate limiting ─────────────────────────────────────────────────────────────

def rate_limited_sleep(seconds: float) -> None:
    """Sleep for a given number of seconds, logging the pause."""
    logger.debug("Rate-limit pause: {:.1f}s", seconds)
    time.sleep(seconds)


# ── Validation helpers ────────────────────────────────────────────────────────

def is_valid_linkedin_url(url: str) -> bool:
    """Return True if url looks like a valid LinkedIn profile URL."""
    return bool(re.match(r"https?://(www\.)?linkedin\.com/in/[^/?#]+", url))


def chunk_list(lst: list[Any], size: int) -> list[list[Any]]:
    """Split a list into chunks of given size."""
    return [lst[i : i + size] for i in range(0, len(lst), size)]
