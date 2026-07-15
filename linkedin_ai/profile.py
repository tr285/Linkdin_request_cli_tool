"""
profile.py — LinkedIn profile page scraper.

Extracts full profile data: headline, about, experience,
skills, certifications, recent posts, and topics.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from playwright.async_api import Page

from linkedin_ai.browser import BrowserManager
from linkedin_ai.cache import Cache
from linkedin_ai.database import Database
from linkedin_ai.models.profile import (
    CertificationItem,
    ExperienceItem,
    PostItem,
    ProfileModel,
)
from linkedin_ai.utils import clean_text, extract_linkedin_id, rate_limited_sleep


async def _safe_text(page: Page, selector: str, default: str = "") -> str:
    """Safely get inner text from a selector."""
    try:
        el = await page.query_selector(selector)
        return clean_text(await el.inner_text()) if el else default
    except Exception:
        return default


async def _scrape_about(page: Page) -> str:
    """Extract the About section."""
    selectors = [
        "div[data-generated-suggestion-target] span[aria-hidden='true']",
        "section.artdeco-card:has(h2:text('About')) div.display-flex span[aria-hidden='true']",
        "#about ~ div span[aria-hidden='true']",
    ]
    for sel in selectors:
        text = await _safe_text(page, sel)
        if text and len(text) > 20:
            return text
    return ""


async def _scrape_experience(page: Page) -> list[ExperienceItem]:
    """Extract experience list."""
    items: list[ExperienceItem] = []
    try:
        # Expand all experience items
        see_more_btns = await page.query_selector_all(
            "section#experience-section button[aria-expanded='false']"
        )
        for btn in see_more_btns:
            await btn.click()
            await asyncio.sleep(0.3)

        exp_els = await page.query_selector_all(
            "li.artdeco-list__item:has(span[class*='pvs-entity'])"
        )
        for el in exp_els[:10]:
            title_el = await el.query_selector("span[aria-hidden='true']")
            title = clean_text(await title_el.inner_text()) if title_el else ""
            company_el = await el.query_selector("span.t-14.t-normal")
            company = clean_text(await company_el.inner_text()) if company_el else ""
            date_el = await el.query_selector("span.t-14.t-normal.t-black--light")
            duration = clean_text(await date_el.inner_text()) if date_el else ""
            if title:
                items.append(ExperienceItem(title=title, company=company, duration=duration))
    except Exception as exc:
        logger.debug("Experience scrape error: {}", exc)
    return items


async def _scrape_skills(page: Page) -> list[str]:
    """Extract skills list."""
    skills: list[str] = []
    try:
        skill_els = await page.query_selector_all(
            "span[class*='skill-categories-taxonomy'],"
            " div[data-view-name='profile-component-entity'] span[aria-hidden='true']"
        )
        for el in skill_els[:30]:
            text = clean_text(await el.inner_text())
            if text and 2 <= len(text) <= 60 and text not in skills:
                skills.append(text)
    except Exception as exc:
        logger.debug("Skills scrape error: {}", exc)
    return skills[:25]


async def _scrape_certifications(page: Page) -> list[CertificationItem]:
    """Extract certifications."""
    certs: list[CertificationItem] = []
    try:
        cert_section = await page.query_selector("#certifications ~ div, section:has(h2:text('Licenses'))")
        if cert_section:
            cert_els = await cert_section.query_selector_all("li span[aria-hidden='true']")
            for i in range(0, len(cert_els) - 1, 2):
                name = clean_text(await cert_els[i].inner_text())
                issuer = clean_text(await cert_els[i + 1].inner_text()) if i + 1 < len(cert_els) else ""
                if name:
                    certs.append(CertificationItem(name=name, issuer=issuer))
    except Exception as exc:
        logger.debug("Certifications scrape error: {}", exc)
    return certs


async def _scrape_recent_posts(page: Page, max_posts: int = 5) -> list[PostItem]:
    """Scrape recent public posts from the activity section."""
    posts: list[PostItem] = []
    try:
        # Navigate to the activity tab
        activity_link = await page.query_selector("a[href*='/recent-activity/']")
        if activity_link:
            href = await activity_link.get_attribute("href")
            if href:
                activity_url = (
                    href if href.startswith("http")
                    else "https://www.linkedin.com" + href
                )
                await page.goto(activity_url + "all/", wait_until="domcontentloaded", timeout=20_000)
                await asyncio.sleep(2)

                post_els = await page.query_selector_all(
                    "div[data-urn*='activity'], div.occludable-update"
                )
                for el in post_els[:max_posts]:
                    text_el = await el.query_selector("span[dir='ltr'], div.feed-shared-text")
                    text = clean_text(await text_el.inner_text()) if text_el else ""
                    if text:
                        posts.append(PostItem(text=text[:500]))
    except Exception as exc:
        logger.debug("Posts scrape error: {}", exc)
    return posts


def _extract_topics(
    posts: list[PostItem],
    skills: list[str],
    headline: str,
    about: str,
) -> list[str]:
    """Extract frequently discussed topics from posts and profile text."""
    # Common tech / business keywords to look for
    topic_patterns = [
        r"\b(AI|machine learning|deep learning|LLM|GPT|neural network)\b",
        r"\b(Python|JavaScript|TypeScript|Rust|Go|Java|C\+\+|Kotlin|Swift)\b",
        r"\b(cloud|AWS|GCP|Azure|Kubernetes|Docker|DevOps|MLOps)\b",
        r"\b(startup|entrepreneurship|founder|venture|VC|funding)\b",
        r"\b(product management|agile|scrum|roadmap|OKR)\b",
        r"\b(data science|analytics|BI|tableau|Power BI)\b",
        r"\b(cybersecurity|security|CISO|pentesting|zero trust)\b",
        r"\b(blockchain|web3|crypto|NFT|DeFi)\b",
        r"\b(UX|UI|design|figma|user research)\b",
        r"\b(leadership|management|culture|DEI|hiring)\b",
    ]

    all_text = " ".join([p.text for p in posts] + [headline, about])
    found: set[str] = set()

    for pattern in topic_patterns:
        matches = re.findall(pattern, all_text, flags=re.IGNORECASE)
        found.update(m.strip() for m in matches)

    # Also add first 5 skills as topics
    for skill in skills[:5]:
        found.add(skill)

    return sorted(found)[:15]


async def scrape_profile(
    url: str,
    manager: BrowserManager,
    db: Database,
    cache: Cache,
    rate_delay: float = 3.0,
    max_posts: int = 5,
) -> ProfileModel | None:
    """
    Scrape a full LinkedIn profile page and persist to DB.

    Returns the ProfileModel or None on failure.
    """
    cache_key = f"profile:{url}"
    cached = cache.get(cache_key)
    if cached:
        logger.info("Profile cache hit: {}", url)
        row = db.get_profile_by_url(url)
        if row:
            return ProfileModel.from_db_dict(row)

    logger.info("Scraping profile: {}", url)
    page = await manager.new_page()

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        rate_limited_sleep(rate_delay)

        # Check for auth wall
        if "authwall" in page.url or "login" in page.url:
            logger.error("Auth wall hit — please run `liai login` first")
            return None

        # ── Extract basic fields ─────────────────────────────────────────────
        name = await _safe_text(page, "h1.text-heading-xlarge, h1[class*='inline']")
        headline = await _safe_text(page, "div.text-body-medium.break-words")
        location = await _safe_text(page, "span.text-body-small.inline.t-black--light.break-words")

        # Company / title from experience top entry
        company_el = await page.query_selector(
            "span[aria-hidden='true'] ~ span.t-14.t-normal span[aria-hidden='true']"
        )
        company = clean_text(await company_el.inner_text()) if company_el else ""

        about = await _scrape_about(page)
        experience = await _scrape_experience(page)
        skills = await _scrape_skills(page)
        certifications = await _scrape_certifications(page)
        recent_posts = await _scrape_recent_posts(page, max_posts=max_posts)
        topics = _extract_topics(recent_posts, skills, headline, about)

        profile = ProfileModel(
            url=url,
            linkedin_id=extract_linkedin_id(url),
            name=name,
            headline=headline,
            about=about,
            company=company or (experience[0].company if experience else ""),
            title=experience[0].title if experience else "",
            location=location,
            skills=skills,
            experience=experience,
            posts=recent_posts,
            certifications=certifications,
            topics=topics,
            post_frequency=f"{len(recent_posts)} recent posts",
            scraped_at=datetime.now(timezone.utc),
        )

        db_id = db.upsert_profile(profile.to_db_dict())
        cache.set(cache_key, True)
        logger.info("Profile scraped and saved | id={} | name={}", db_id, name)
        return profile

    except Exception as exc:
        logger.error("Profile scrape failed for {}: {}", url, exc)
        return None
    finally:
        await page.close()
