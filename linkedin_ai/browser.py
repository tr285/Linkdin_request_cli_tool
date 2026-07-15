"""
browser.py — Playwright browser context factory.

Provides a persistent browser context that saves cookies between
sessions. Supports both headless and headed modes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import AsyncGenerator

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


class BrowserManager:
    """Manages a Playwright Chromium browser instance with persistent storage."""

    def __init__(
        self,
        cookies_path: str | Path = ".liai_session.json",
        headless: bool = False,
        slow_mo: int = 500,
    ) -> None:
        self.cookies_path = Path(cookies_path)
        self.headless = headless
        self.slow_mo = slow_mo
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> BrowserContext:
        """Launch browser and return a configured context."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=["--disable-blink-features=AutomationControlled"],
        )

        # Build context with anti-detection viewport & user agent
        context_kwargs: dict = {
            "viewport": {"width": 1280, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "java_script_enabled": True,
            "accept_downloads": False,
        }

        self._context = await self._browser.new_context(**context_kwargs)

        # Inject anti-bot evasion script
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """)

        # Restore saved cookies if available
        if self.cookies_path.exists():
            try:
                import json
                cookies = json.loads(self.cookies_path.read_text(encoding="utf-8"))
                await self._context.add_cookies(cookies)
                logger.info("Loaded {} cookies from {}", len(cookies), self.cookies_path)
            except Exception as exc:
                logger.warning("Could not load cookies: {}", exc)

        logger.info("Browser started | headless={}", self.headless)
        return self._context

    async def new_page(self) -> Page:
        """Return a new page from the active context."""
        if self._context is None:
            await self.start()
        assert self._context is not None
        page = await self._context.new_page()
        # Block unnecessary resource types for speed
        await page.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in ("image", "font", "media")
            else route.continue_(),
        )
        return page

    async def save_cookies(self) -> None:
        """Persist current session cookies to disk."""
        if self._context is None:
            return
        import json
        cookies = await self._context.cookies()
        self.cookies_path.write_text(
            json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("Saved {} cookies to {}", len(cookies), self.cookies_path)

    async def stop(self) -> None:
        """Save cookies and close the browser."""
        await self.save_cookies()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser stopped")

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.stop()
