"""
tests/test_ai.py — Unit tests for AIAnalyzer with mocked OpenAI responses.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from linkedin_ai.ai import AIAnalyzer
from linkedin_ai.models.analysis import AnalysisResult
from linkedin_ai.models.profile import ProfileModel


MOCK_AI_RESPONSE = {
    "summary": "Jane is an experienced ML engineer specializing in NLP.",
    "interests": ["AI Research", "Open Source", "Mentoring"],
    "networking_score": 8.5,
    "score_rationale": "Strong public presence and relevant technical expertise.",
    "conversation_starters": [
        "What's your approach to fine-tuning LLMs for production?",
        "How do you handle data quality in your ML pipelines?",
    ],
    "connection_note": "Hi Jane, your work on LLM fine-tuning caught my eye. Would love to connect!",
    "follow_up_drafts": ["Great to connect, Jane! Would love to hear more about your NLP work."],
    "suggested_questions": ["What open-source tools do you rely on most in your ML workflow?"],
}


def _make_mock_response(content: dict) -> MagicMock:
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(content)
    mock_usage = MagicMock()
    mock_usage.total_tokens = 512
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = mock_usage
    return mock_response


class TestAIAnalyzer:
    @pytest.fixture
    def analyzer(self) -> AIAnalyzer:
        return AIAnalyzer(api_key="sk-test-key", model="gpt-4o-mini")

    def test_analyze_profile_returns_result(
        self, analyzer: AIAnalyzer, sample_profile: ProfileModel
    ) -> None:
        mock_response = _make_mock_response(MOCK_AI_RESPONSE)

        with patch.object(analyzer._client.chat.completions, "create", return_value=mock_response):
            result = analyzer.analyze_profile(sample_profile, profile_id=1)

        assert isinstance(result, AnalysisResult)
        assert result.networking_score == 8.5
        assert result.profile_id == 1
        assert "LLM" in result.connection_note or "Jane" in result.connection_note

    def test_connection_note_length_enforced(
        self, analyzer: AIAnalyzer, sample_profile: ProfileModel
    ) -> None:
        long_note_response = {**MOCK_AI_RESPONSE, "connection_note": "X" * 500}
        mock_response = _make_mock_response(long_note_response)

        with patch.object(analyzer._client.chat.completions, "create", return_value=mock_response):
            result = analyzer.analyze_profile(sample_profile, profile_id=1)

        assert len(result.connection_note) <= 300

    def test_analyze_profile_handles_api_error(
        self, analyzer: AIAnalyzer, sample_profile: ProfileModel
    ) -> None:
        from openai import APIError

        with patch.object(
            analyzer._client.chat.completions,
            "create",
            side_effect=APIError("API failed", request=MagicMock(), body=None),
        ):
            result = analyzer.analyze_profile(sample_profile, profile_id=1)

        # Should return empty result rather than crashing
        assert isinstance(result, AnalysisResult)
        assert result.networking_score == 0.0
        assert result.summary == ""

    def test_networking_score_clamped(
        self, analyzer: AIAnalyzer, sample_profile: ProfileModel
    ) -> None:
        bad_score_response = {**MOCK_AI_RESPONSE, "networking_score": 99.9}
        mock_response = _make_mock_response(bad_score_response)

        with patch.object(analyzer._client.chat.completions, "create", return_value=mock_response):
            result = analyzer.analyze_profile(sample_profile, profile_id=1)

        assert result.networking_score <= 10.0

    def test_refine_connection_note(
        self, analyzer: AIAnalyzer, sample_profile: ProfileModel
    ) -> None:
        refined_response = {"note": "Hi Jane, your NLP research is fascinating. Would love to connect!"}
        mock_response = _make_mock_response(refined_response)

        with patch.object(analyzer._client.chat.completions, "create", return_value=mock_response):
            note = analyzer.refine_connection_note(
                sample_profile, "original note", "make it more specific"
            )

        assert "Jane" in note
        assert len(note) <= 300

    def test_tokens_tracked(
        self, analyzer: AIAnalyzer, sample_profile: ProfileModel
    ) -> None:
        mock_response = _make_mock_response(MOCK_AI_RESPONSE)

        with patch.object(analyzer._client.chat.completions, "create", return_value=mock_response):
            result = analyzer.analyze_profile(sample_profile, profile_id=1)

        assert result.ai_tokens_used == 512
        assert result.ai_model == "gpt-4o-mini"
