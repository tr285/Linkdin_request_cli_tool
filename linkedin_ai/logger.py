"""
logger.py — Loguru multi-sink logging configuration.

Sinks:
  - logs/daily/YYYY-MM-DD.log   (INFO+, daily rotation)
  - logs/errors/errors.log       (ERROR+, 10 MB rotation)
  - logs/ai/ai_calls.log         (AI-tagged messages)
  - logs/debug/debug.log         (DEBUG+, dev mode)
  - stderr                       (WARNING+, colourised)
"""

import sys
from pathlib import Path
from loguru import logger as _logger


def setup_logging(log_dir: str | Path = "logs", log_level: str = "INFO", debug: bool = False) -> None:
    """Configure all Loguru sinks. Call once at app startup."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    (log_path / "daily").mkdir(exist_ok=True)
    (log_path / "errors").mkdir(exist_ok=True)
    (log_path / "ai").mkdir(exist_ok=True)
    (log_path / "debug").mkdir(exist_ok=True)

    _logger.remove()  # Remove default stderr handler

    # ── stderr — colourised WARNING+ ─────────────────────────────────────────
    _logger.add(
        sys.stderr,
        level="WARNING",
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> — <level>{message}</level>",
    )

    # ── daily rotating log ───────────────────────────────────────────────────
    _logger.add(
        str(log_path / "daily" / "{time:YYYY-MM-DD}.log"),
        level=log_level,
        rotation="00:00",      # New file each midnight
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} — {message}",
        enqueue=True,
    )

    # ── error-only log ───────────────────────────────────────────────────────
    _logger.add(
        str(log_path / "errors" / "errors.log"),
        level="ERROR",
        rotation="10 MB",
        retention="60 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line}\n{message}\n{exception}",
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )

    # ── AI interaction log (filter by custom tag) ────────────────────────────
    _logger.add(
        str(log_path / "ai" / "ai_calls.log"),
        level="DEBUG",
        filter=lambda record: "AI" in record["extra"],
        rotation="50 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {extra[AI]} | {message}",
        enqueue=True,
    )

    # ── debug log (only in debug mode) ──────────────────────────────────────
    if debug:
        _logger.add(
            str(log_path / "debug" / "debug.log"),
            level="DEBUG",
            rotation="20 MB",
            retention="7 days",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} — {message}",
            enqueue=True,
        )

    _logger.info("Logging initialised | log_dir={} | level={}", log_path.resolve(), log_level)


# Convenience: AI-tagged logger
ai_logger = _logger.bind(AI="AI_CALL")
