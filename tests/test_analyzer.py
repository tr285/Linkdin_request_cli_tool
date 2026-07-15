"""
tests/test_analyzer.py — Unit tests for ProfileAnalyzer.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from linkedin_ai.analyzer import ProfileAnalyzer
from linkedin_ai.models.analysis import AnalysisResult
from linkedin_ai.models.profile import ProfileModel


class TestProfileAnalyzer:
    def test_analyze_one_missing_profile(self, tmp_db) -> None:
        mock_ai = MagicMock()
        analyzer = ProfileAnalyzer(db=tmp_db, ai=mock_ai)
        result = analyzer.analyze_one(profile_id=9999)
        assert result is None
        mock_ai.analyze_profile.assert_not_called()

    def test_analyze_one_stores_result(
        self, tmp_db, sample_profile: ProfileModel
    ) -> None:
        pid = tmp_db.upsert_profile(sample_profile.to_db_dict())

        mock_ai = MagicMock()
        mock_ai.analyze_profile.return_value = AnalysisResult(
            profile_id=pid,
            profile_name=sample_profile.name,
            networking_score=8.5,
            connection_note="Hi Jane!",
            summary="Experienced ML engineer.",
        )

        analyzer = ProfileAnalyzer(db=tmp_db, ai=mock_ai)
        result = analyzer.analyze_one(pid)

        assert result is not None
        assert result.networking_score == 8.5
        # Verify it was persisted
        analysis = tmp_db.get_analysis(pid)
        assert analysis is not None
        assert analysis["networking_score"] == 8.5
        # Verify profile status updated
        profile_row = tmp_db.get_profile(pid)
        assert profile_row["status"] == "analyzed"

    def test_analyze_batch_skips_existing(
        self, tmp_db, sample_profile: ProfileModel
    ) -> None:
        pid = tmp_db.upsert_profile(sample_profile.to_db_dict())
        # Pre-save analysis
        tmp_db.save_analysis({"profile_id": pid, "networking_score": 7.0})

        mock_ai = MagicMock()
        analyzer = ProfileAnalyzer(db=tmp_db, ai=mock_ai)
        results = analyzer.analyze_batch([pid], skip_existing=True)

        assert results == []
        mock_ai.analyze_profile.assert_not_called()

    def test_analyze_batch_reanalyze_flag(
        self, tmp_db, sample_profile: ProfileModel
    ) -> None:
        pid = tmp_db.upsert_profile(sample_profile.to_db_dict())
        tmp_db.save_analysis({"profile_id": pid, "networking_score": 7.0})

        mock_ai = MagicMock()
        mock_ai.analyze_profile.return_value = AnalysisResult(
            profile_id=pid, profile_name="Jane", networking_score=9.0
        )

        analyzer = ProfileAnalyzer(db=tmp_db, ai=mock_ai)
        results = analyzer.analyze_batch([pid], skip_existing=False)

        assert len(results) == 1
        mock_ai.analyze_profile.assert_called_once()

    def test_get_top_profiles_sorted_by_score(self, tmp_db) -> None:
        for i, score in enumerate([3.0, 7.5, 9.0, 5.0]):
            pid = tmp_db.upsert_profile({"url": f"https://linkedin.com/in/u{i}", "name": f"User{i}"})
            tmp_db.save_analysis({"profile_id": pid, "networking_score": score})

        mock_ai = MagicMock()
        analyzer = ProfileAnalyzer(db=tmp_db, ai=mock_ai)
        top = analyzer.get_top_profiles(limit=3)

        scores = [r.get("networking_score") for r in top]
        assert scores == sorted(scores, reverse=True)

    def test_compute_aggregate_stats_empty(self, tmp_db) -> None:
        mock_ai = MagicMock()
        analyzer = ProfileAnalyzer(db=tmp_db, ai=mock_ai)
        stats = analyzer.compute_aggregate_stats()
        assert stats == {}

    def test_compute_aggregate_stats_with_data(self, tmp_db) -> None:
        for i, score in enumerate([6.0, 8.0, 4.0]):
            pid = tmp_db.upsert_profile({"url": f"https://linkedin.com/in/u{i}", "company": "ACME"})
            tmp_db.save_analysis({"profile_id": pid, "networking_score": score})

        mock_ai = MagicMock()
        analyzer = ProfileAnalyzer(db=tmp_db, ai=mock_ai)
        stats = analyzer.compute_aggregate_stats()

        assert stats["total_analyzed"] == 3
        assert stats["avg_score"] == pytest.approx(6.0)
        assert stats["max_score"] == 8.0
        assert stats["min_score"] == 4.0
