"""
models/search.py — Search filter model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


ExperienceLevel = Literal["entry", "associate", "mid-senior", "director", "executive", "any"]


class SearchFilter(BaseModel):
    """Filter parameters for a LinkedIn people search."""

    # Content filters
    keywords: str = ""
    domain: str = ""
    industry: str = ""
    company: str = ""
    title: str = ""
    skills: list[str] = Field(default_factory=list)

    # Location
    country: str = ""
    city: str = ""

    # Experience
    experience_level: ExperienceLevel = "any"

    # Pagination
    max_results: int = Field(default=50, ge=1, le=200)

    @field_validator("skills", mode="before")
    @classmethod
    def _parse_skills(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v)  # type: ignore[arg-type]

    def to_search_url(self) -> str:
        """Build a LinkedIn search URL from filters."""
        base = "https://www.linkedin.com/search/results/people/?"
        parts: list[str] = []
        if self.keywords:
            parts.append(f"keywords={self.keywords.replace(' ', '%20')}")
        if self.title:
            parts.append(f"title={self.title.replace(' ', '%20')}")
        if self.company:
            parts.append(f"company={self.company.replace(' ', '%20')}")
        # LinkedIn uses geoUrn codes; we'll pass city as keywords fallback
        if self.city and not self.keywords:
            parts.append(f"keywords={self.city.replace(' ', '%20')}")
        return base + "&".join(parts) if parts else base + "keywords=software+engineer"

    def summary(self) -> str:
        """Human-readable summary of filters."""
        parts = []
        if self.keywords:
            parts.append(f"keywords='{self.keywords}'")
        if self.title:
            parts.append(f"title='{self.title}'")
        if self.company:
            parts.append(f"company='{self.company}'")
        if self.industry:
            parts.append(f"industry='{self.industry}'")
        if self.country:
            parts.append(f"country='{self.country}'")
        if self.city:
            parts.append(f"city='{self.city}'")
        if self.skills:
            parts.append(f"skills=[{', '.join(self.skills)}]")
        if self.experience_level != "any":
            parts.append(f"experience='{self.experience_level}'")
        return " | ".join(parts) or "no filters"
