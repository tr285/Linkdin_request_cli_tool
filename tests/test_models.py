"""
tests/test_models.py — Unit tests for Pydantic models.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from linkedin_ai.models.profile import ProfileModel, ExperienceItem
from linkedin_ai.models.search import SearchFilter
from linkedin_ai.models.analysis import AnalysisResult
from linkedin_ai.models.report import ReportRow


class TestProfileModel:
    def test_basic_construction(self, sample_profile: ProfileModel) -> None:
        assert sample_profile.name == "Jane Doe"
        assert sample_profile.linkedin_id == "jane-doe-ai"

    def test_url_trailing_slash_stripped(self) -> None:
        p = ProfileModel(url="https://linkedin.com/in/user/")
        assert p.url == "https://linkedin.com/in/user"

    def test_display_name_fallback(self) -> None:
        p = ProfileModel(url="https://linkedin.com/in/user123", linkedin_id="user123")
        assert p.display_name == "user123"

    def test_skills_str(self, sample_profile: ProfileModel) -> None:
        assert "Python" in sample_profile.skills_str

    def test_to_db_dict_serializes_lists(self, sample_profile: ProfileModel) -> None:
        d = sample_profile.to_db_dict()
        skills = json.loads(d["skills_json"])
        assert isinstance(skills, list)
        assert "Python" in skills

    def test_from_db_dict_roundtrip(self, sample_profile: ProfileModel) -> None:
        d = sample_profile.to_db_dict()
        restored = ProfileModel.from_db_dict(d)
        assert restored.name == sample_profile.name
        assert restored.skills == sample_profile.skills


class TestSearchFilter:
    def test_skills_from_comma_string(self) -> None:
        f = SearchFilter(skills="Python, Go, Rust")
        assert f.skills == ["Python", "Go", "Rust"]

    def test_max_results_clamped(self) -> None:
        f = SearchFilter(max_results=200)
        assert f.max_results == 200

    def test_max_results_min_bound(self) -> None:
        with pytest.raises(ValidationError):
            SearchFilter(max_results=0)

    def test_summary_output(self, sample_search_filter: SearchFilter) -> None:
        summary = sample_search_filter.summary()
        assert "ML Engineer" in summary
        assert "TechCorp" in summary

    def test_to_search_url_contains_keywords(self) -> None:
        f = SearchFilter(keywords="machine learning", title="engineer")
        url = f.to_search_url()
        assert "linkedin.com/search/results/people/" in url


class TestAnalysisResult:
    def test_connection_note_truncated_to_300(self) -> None:
        long_note = "A" * 500
        result = AnalysisResult(profile_id=1, connection_note=long_note)
        assert len(result.connection_note) == 300

    def test_networking_score_clamped_above_10(self) -> None:
        result = AnalysisResult(profile_id=1, networking_score=15.0)
        assert result.networking_score == 10.0

    def test_networking_score_clamped_below_0(self) -> None:
        result = AnalysisResult(profile_id=1, networking_score=-1.0)
        assert result.networking_score == 0.0

    def test_score_label_excellent(self) -> None:
        result = AnalysisResult(profile_id=1, networking_score=9.0)
        assert result.score_label == "Excellent"

    def test_score_label_good(self) -> None:
        result = AnalysisResult(profile_id=1, networking_score=7.0)
        assert result.score_label == "Good"

    def test_score_label_fair(self) -> None:
        result = AnalysisResult(profile_id=1, networking_score=5.0)
        assert result.score_label == "Fair"

    def test_score_label_low(self) -> None:
        result = AnalysisResult(profile_id=1, networking_score=2.0)
        assert result.score_label == "Low"

    def test_score_colour_green_above_8(self) -> None:
        result = AnalysisResult(profile_id=1, networking_score=8.5)
        assert result.score_colour == "bright_green"

    def test_to_db_dict_structure(self, sample_analysis: AnalysisResult) -> None:
        d = sample_analysis.to_db_dict()
        assert "profile_id" in d
        assert "networking_score" in d
        assert "connection_note" in d
        interests = json.loads(d["interests_json"])
        assert isinstance(interests, list)


class TestReportRow:
    def test_default_construction(self) -> None:
        row = ReportRow()
        assert row.profile_id == 0
        assert row.networking_score == 0.0
        assert row.status == "new"

    def test_full_construction(self, sample_analysis: AnalysisResult) -> None:
        row = ReportRow(
            profile_id=sample_analysis.profile_id,
            name=sample_analysis.profile_name,
            networking_score=sample_analysis.networking_score,
            connection_note=sample_analysis.connection_note,
            status="approved",
        )
        assert row.networking_score == 8.5
        assert row.status == "approved"
