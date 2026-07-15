"""
models/report.py — Flat report row model for export.
"""

from __future__ import annotations

from pydantic import BaseModel


class ReportRow(BaseModel):
    """Flattened profile + analysis view for CSV/Excel/JSON/HTML export."""

    profile_id: int = 0
    name: str = ""
    url: str = ""
    headline: str = ""
    company: str = ""
    title: str = ""
    location: str = ""
    industry: str = ""
    skills: str = ""          # comma-separated
    experience_count: int = 0
    post_count: int = 0
    topics: str = ""          # comma-separated
    status: str = "new"
    networking_score: float = 0.0
    score_label: str = ""
    summary: str = ""
    interests: str = ""       # comma-separated
    connection_note: str = ""
    conversation_starters: str = ""  # first starter
    analyzed_at: str = ""
    scraped_at: str = ""
