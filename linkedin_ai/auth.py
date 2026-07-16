"""
auth.py — LinkedIn session management.

Guides the user through a manual login flow (no credentials are
stored). Checks whether an existing session is still valid and
persists cookies for reuse.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from loguru import logger
from playwright.async_api import Page

from linkedin_ai.browser import BrowserManager


LINKEDIN_HOME = "https://www.linkedin.com"
LINKEDIN_FEED = "https://www.linkedin.com/feed/"
LOGIN_CHECK_SELECTOR = "div[data-control-name='identity_welcome_message'], a[href*='/in/me']"
SESSION_TIMEOUT = 8_000  # ms — reduced from 20 000; fail-fast when not authenticated


async def is_logged_in(page: Page) -> bool:
    """Return True if the current page session is authenticated."""
    try:
        await page.goto(LINKEDIN_FEED, wait_until="domcontentloaded", timeout=30_000)
        # If we end up on the login page we're not authenticated
        if "login" in page.url or "authwall" in page.url:
            return False
        # Look for any feed-specific element (selector broadened for LinkedIn UI changes)
        await page.wait_for_selector(
            "div.feed-identity-module, div[data-view-name='feed-tabs'], "
            "div.scaffold-layout__main, div[data-finite-scroll-hotspot='top']",
            timeout=SESSION_TIMEOUT,
        )
        return True
    except Exception:
        return False


async def login_flow(manager: BrowserManager) -> bool:
    """
    Open LinkedIn in the browser and wait for the user to log in manually.
    Auto-detects login by polling the page URL — no ENTER press needed.
    Returns True when authentication is detected.
    """
    page = await manager.new_page()
    logger.info("Opening LinkedIn for manual login")

    await page.goto(LINKEDIN_HOME + "/login", wait_until="domcontentloaded", timeout=30_000)

    print("\n" + "─" * 60)
    print("  LinkedIn is open in your browser.")
    print("  Please log in — this window will close automatically.")
    print("─" * 60)

    # Poll every 2 s until the feed URL appears (max 3 minutes)
    max_wait_seconds = 180
    poll_interval = 2
    elapsed = 0
    logged_in = False

    while elapsed < max_wait_seconds:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        current_url = page.url
        if "/feed" in current_url or "/mynetwork" in current_url or "/in/me" in current_url:
            logged_in = True
            break
        if "login" not in current_url and "authwall" not in current_url and "checkpoint" not in current_url:
            # We've navigated away from login pages — do a final check
            logged_in = await is_logged_in(page)
            if logged_in:
                break

    if logged_in:
        await manager.save_cookies()
        logger.info("Login successful — session saved")
    else:
        logger.warning("Login timed out or could not be confirmed.")

    return logged_in


async def verify_session(manager: BrowserManager) -> bool:
    """Check if stored cookies give a valid authenticated session."""
    page = await manager.new_page()
    try:
        result = await is_logged_in(page)
    finally:
        await page.close()
    return result


def import_cookies_from_file(src: str | Path, dest: str | Path) -> int:
    """
    Copy a cookies JSON file exported from a browser extension
    (e.g. 'Cookie-Editor') into the session file used by liai.

    Returns the number of cookies imported.
    Raises ValueError if the file is not valid JSON or not a list.
    """
    src, dest = Path(src), Path(dest)
    raw = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Expected a JSON array of cookie objects")
    dest.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Imported {} cookies from {} → {}", len(raw), src, dest)
    return len(raw)
