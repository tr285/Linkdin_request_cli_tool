"""
auth.py — LinkedIn session management.

Guides the user through a manual login flow (no credentials are
stored). Checks whether an existing session is still valid and
persists cookies for reuse.
"""

from __future__ import annotations

import asyncio

from loguru import logger
from playwright.async_api import Page

from linkedin_ai.browser import BrowserManager


LINKEDIN_HOME = "https://www.linkedin.com"
LINKEDIN_FEED = "https://www.linkedin.com/feed/"
LOGIN_CHECK_SELECTOR = "div[data-control-name='identity_welcome_message'], a[href*='/in/me']"
SESSION_TIMEOUT = 20_000  # ms


async def is_logged_in(page: Page) -> bool:
    """Return True if the current page session is authenticated."""
    try:
        await page.goto(LINKEDIN_FEED, wait_until="domcontentloaded", timeout=30_000)
        # If we end up on the login page we're not authenticated
        if "login" in page.url or "authwall" in page.url:
            return False
        # Look for feed-specific elements
        await page.wait_for_selector(
            "div.feed-identity-module, div[data-view-name='feed-tabs']",
            timeout=SESSION_TIMEOUT,
        )
        return True
    except Exception:
        return False


async def login_flow(manager: BrowserManager) -> bool:
    """
    Open LinkedIn in the browser and wait for the user to log in manually.
    Returns True when authentication is detected.
    """
    page = await manager.new_page()
    logger.info("Opening LinkedIn for manual login")

    await page.goto(LINKEDIN_HOME + "/login", wait_until="domcontentloaded", timeout=30_000)

    print("\n" + "─" * 60)
    print("  LinkedIn is open in your browser.")
    print("  Please log in manually, then press ENTER here.")
    print("─" * 60)
    input()

    # Verify login succeeded
    success = await is_logged_in(page)
    if success:
        await manager.save_cookies()
        logger.info("Login successful — session saved")
    else:
        logger.warning("Could not confirm login. Please try again.")

    return success


async def verify_session(manager: BrowserManager) -> bool:
    """Check if stored cookies give a valid authenticated session."""
    page = await manager.new_page()
    result = await is_logged_in(page)
    await page.close()
    return result
