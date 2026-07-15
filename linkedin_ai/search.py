"""
search.py — LinkedIn people search scraper.

Navigates LinkedIn's people search with filter support,
extracts result cards, and stores profiles in SQLite.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from loguru import logger
from playwright.async_api import Page

from linkedin_ai.browser import BrowserManager
from linkedin_ai.cache import Cache
from linkedin_ai.database import Database
from linkedin_ai.models.profile import ProfileModel
from linkedin_ai.models.search import SearchFilter
from linkedin_ai.utils import rate_limited_sleep, extract_linkedin_id


SEARCH_BASE = "https://www.linkedin.com/search/results/people/"


def _build_search_url(filters: SearchFilter) -> str:
    """Construct a LinkedIn people-search URL from a SearchFilter."""
    params: list[str] = []

    keywords_parts = []
    if filters.keywords:
        keywords_parts.append(filters.keywords)
    if filters.title:
        keywords_parts.append(filters.title)
    if filters.city:
        keywords_parts.append(filters.city)
    if keywords_parts:
        kw = " ".join(keywords_parts).replace(" ", "%20")
        params.append(f"keywords={kw}")

    if filters.company:
        params.append(f"company={filters.company.replace(' ', '%20')}")

    # Experience level mapping
    exp_map = {
        "entry": "1", "associate": "2", "mid-senior": "3",
        "director": "4", "executive": "5", "any": "",
    }
    exp_code = exp_map.get(filters.experience_level, "")
    if exp_code:
        params.append(f"f_E={exp_code}")

    return SEARCH_BASE + ("?" + "&".join(params) if params else "")


async def _extract_result_cards(page: Page) -> list[dict[str, Any]]:
    """Extract profile cards from a search results page."""
    results: list[dict[str, Any]] = []

    # Wait for search results to load
    try:
        await page.wait_for_selector(
            "li.reusable-search__result-container, li[class*='search-result']",
            timeout=15_000,
        )
    except Exception:
        logger.warning("No search result cards found on page")
        return results

    cards = await page.query_selector_all(
        "li.reusable-search__result-container, li[class*='search-result']"
    )

    for card in cards:
        try:
            # Name
            name_el = await card.query_selector(
                "span[aria-hidden='true'], .entity-result__title-text a span[aria-hidden]"
            )
            name = (await name_el.inner_text()).strip() if name_el else ""

            # Headline
            headline_el = await card.query_selector(
                ".entity-result__primary-subtitle, [class*='subline-level-1']"
            )
            headline = (await headline_el.inner_text()).strip() if headline_el else ""

            # Location
            location_el = await card.query_selector(
                ".entity-result__secondary-subtitle, [class*='subline-level-2']"
            )
            location = (await location_el.inner_text()).strip() if location_el else ""

            # Profile link
            link_el = await card.query_selector("a[href*='/in/']")
            href = await link_el.get_attribute("href") if link_el else ""
            url = ""
            if href:
                match = re.search(r"(https?://[^?]+linkedin\.com/in/[^/?]+)", href)
                url = match.group(1) if match else ""
                if not url and href.startswith("/in/"):
                    url = "https://www.linkedin.com" + href.split("?")[0]

            if url and name:
                results.append({
                    "url": url.rstrip("/"),
                    "linkedin_id": extract_linkedin_id(url),
                    "name": name,
                    "headline": headline,
                    "location": location,
                })
        except Exception as exc:
            logger.debug("Error parsing card: {}", exc)
            continue

    return results


async def search_profiles(
    manager: BrowserManager,
    filters: SearchFilter,
    db: Database,
    cache: Cache,
    rate_delay: float = 3.0,
) -> list[int]:
    """
    Run a LinkedIn people search with given filters.

    Returns a list of profile row IDs stored in the database.
    """
    cache_key = f"search:{filters.model_dump_json()}"
    cached = cache.get(cache_key)
    if cached:
        logger.info("Returning cached search results")
        return cached

    url = _build_search_url(filters)
    logger.info("Starting search | url={} | max={}", url, filters.max_results)

    page = await manager.new_page()
    profile_ids: list[int] = []
    collected: list[dict[str, Any]] = []
    current_page = 1

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        rate_limited_sleep(rate_delay)

        while len(collected) < filters.max_results:
            cards = await _extract_result_cards(page)
            if not cards:
                logger.info("No more results found at page {}", current_page)
                break

            collected.extend(cards)
            logger.info("Page {}: found {} cards (total {})", current_page, len(cards), len(collected))

            if len(collected) >= filters.max_results:
                break

            # Click "Next" pagination button
            next_btn = await page.query_selector(
                "button[aria-label='Next']"
            )
            if not next_btn or not await next_btn.is_enabled():
                break
            await next_btn.click()
            rate_limited_sleep(rate_delay)
            current_page += 1

    except Exception as exc:
        logger.error("Search scraping error: {}", exc)
    finally:
        await page.close()

    # Trim to max_results and save to DB
    for card in collected[: filters.max_results]:
        profile = ProfileModel(
            url=card["url"],
            linkedin_id=card.get("linkedin_id", ""),
            name=card.get("name", ""),
            headline=card.get("headline", ""),
            location=card.get("location", ""),
        )
        profile_id = db.upsert_profile(profile.to_db_dict())
        profile_ids.append(profile_id)

    # Save search record
    search_id = db.save_search(filters.model_dump(), len(profile_ids))
    for pid in profile_ids:
        db.link_search_result(search_id, pid)

    cache.set(cache_key, profile_ids)
    logger.info("Search complete: {} profiles stored", len(profile_ids))
    return profile_ids
