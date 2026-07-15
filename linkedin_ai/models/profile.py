"""
models/profile.py — LinkedIn profile data model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class ExperienceItem(BaseModel):
    title: str = ""
    company: str = ""
    duration: str = ""
    description: str = ""
    is_current: bool = False


class PostItem(BaseModel):
    text: str = ""
    date: str = ""
    likes: int = 0
    comments: int = 0
    url: str = ""


class CertificationItem(BaseModel):
    name: str = ""
    issuer: str = ""
    issued_date: str = ""


class ProfileModel(BaseModel):
    """Full LinkedIn profile data model."""

    # Identity
    url: str
    linkedin_id: str = ""
    name: str = ""
    headline: str = ""
    about: str = ""

    # Current position
    company: str = ""
    title: str = ""
    location: str = ""
    country: str = ""
    industry: str = ""

    # Structured data
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    posts: list[PostItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)  # Frequently discussed topics
    post_frequency: str = ""

    # Metadata
    status: str = "new"
    scraped_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("url", mode="before")
    @classmethod
    def _clean_url(cls, v: str) -> str:
        return v.rstrip("/").strip()

    @property
    def display_name(self) -> str:
        return self.name or self.linkedin_id or self.url

    @property
    def skills_str(self) -> str:
        return ", ".join(self.skills[:10])

    @property
    def years_experience(self) -> int:
        """Rough total years of experience from experience list."""
        return len(self.experience)

    def to_db_dict(self) -> dict[str, Any]:
        """Serialize to flat dict suitable for database.upsert_profile."""
        import json
        return {
            "url": self.url,
            "linkedin_id": self.linkedin_id,
            "name": self.name,
            "headline": self.headline,
            "about": self.about,
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "country": self.country,
            "industry": self.industry,
            "skills_json": json.dumps(self.skills),
            "experience_json": json.dumps([e.model_dump() for e in self.experience]),
            "posts_json": json.dumps([p.model_dump() for p in self.posts]),
            "certifications_json": json.dumps([c.model_dump() for c in self.certifications]),
            "topics_json": json.dumps(self.topics),
            "post_frequency": self.post_frequency,
            "status": self.status,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }

    @classmethod
    def from_db_dict(cls, row: dict[str, Any]) -> "ProfileModel":
        """Reconstruct a ProfileModel from a database row."""
        import json
        return cls(
            url=row.get("url", ""),
            linkedin_id=row.get("linkedin_id") or "",
            name=row.get("name") or "",
            headline=row.get("headline") or "",
            about=row.get("about") or "",
            company=row.get("company") or "",
            title=row.get("title") or "",
            location=row.get("location") or "",
            country=row.get("country") or "",
            industry=row.get("industry") or "",
            skills=json.loads(row.get("skills_json") or "[]"),
            experience=[ExperienceItem(**e) for e in json.loads(row.get("experience_json") or "[]")],
            posts=[PostItem(**p) for p in json.loads(row.get("posts_json") or "[]")],
            certifications=[CertificationItem(**c) for c in json.loads(row.get("certifications_json") or "[]")],
            topics=json.loads(row.get("topics_json") or "[]"),
            post_frequency=row.get("post_frequency") or "",
            status=row.get("status") or "new",
        )
