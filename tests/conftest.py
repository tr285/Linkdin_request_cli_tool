"""
tests/conftest.py — Shared pytest fixtures.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from linkedin_ai.database import Database
from linkedin_ai.cache import Cache
from linkedin_ai.models.profile import ProfileModel, ExperienceItem, PostItem
from linkedin_ai.models.search import SearchFilter
from linkedin_ai.models.analysis import AnalysisResult
from linkedin_ai.config import AppConfig


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """Fresh in-memory-style SQLite DB in a temp directory."""
    return Database(db_path=tmp_path / "test.db")


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Cache:
    """Cache pointing to a temp directory."""
    return Cache(cache_dir=tmp_path / "cache", ttl_hours=1)


@pytest.fixture
def sample_profile() -> ProfileModel:
    return ProfileModel(
        url="https://www.linkedin.com/in/jane-doe-ai",
        linkedin_id="jane-doe-ai",
        name="Jane Doe",
        headline="Senior ML Engineer at TechCorp | AI Enthusiast",
        about="Building AI-powered products. Passionate about NLP and computer vision.",
        company="TechCorp",
        title="Senior ML Engineer",
        location="San Francisco, CA",
        country="United States",
        industry="Technology",
        skills=["Python", "TensorFlow", "PyTorch", "NLP", "Computer Vision"],
        experience=[
            ExperienceItem(title="Senior ML Engineer", company="TechCorp", duration="2022–Present", is_current=True),
            ExperienceItem(title="Data Scientist", company="DataLabs", duration="2019–2022"),
        ],
        posts=[
            PostItem(text="Excited to share our new paper on LLM fine-tuning!", likes=120),
            PostItem(text="Great talk at AI Summit this week on responsible AI.", likes=85),
        ],
        certifications=[],
        topics=["AI", "Machine Learning", "NLP", "Python", "LLMs"],
        post_frequency="2 recent posts",
    )


@pytest.fixture
def sample_analysis(sample_profile: ProfileModel) -> AnalysisResult:
    return AnalysisResult(
        profile_id=1,
        profile_url=sample_profile.url,
        profile_name=sample_profile.name,
        summary="Jane is an experienced ML engineer with deep expertise in NLP and computer vision.",
        interests=["AI Research", "Open Source", "Teaching"],
        networking_score=8.5,
        score_rationale="Strong technical background, active online presence, shares expertise publicly.",
        conversation_starters=[
            "I saw your post on LLM fine-tuning — what approach worked best for your use case?",
            "How do you see responsible AI shaping product development at TechCorp?",
        ],
        connection_note="Hi Jane, I admire your work in NLP. I'm working on similar challenges and would love to connect!",
        follow_up_drafts=["Great to connect! Would love to hear more about your LLM work."],
        suggested_questions=["What's your take on the current state of open-source LLMs?"],
    )


@pytest.fixture
def sample_search_filter() -> SearchFilter:
    return SearchFilter(
        keywords="machine learning",
        title="ML Engineer",
        company="TechCorp",
        industry="Technology",
        country="United States",
        city="San Francisco",
        skills=["Python", "TensorFlow"],
        experience_level="mid-senior",
        max_results=10,
    )
