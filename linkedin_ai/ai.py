"""
ai.py — OpenAI API integration for profile analysis.

All AI calls go through this module. Prompts are structured for
consistent, parseable JSON responses. Retries are built-in.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from openai import OpenAI, APIError, RateLimitError, APITimeoutError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from linkedin_ai.logger import ai_logger
from linkedin_ai.models.analysis import AnalysisResult
from linkedin_ai.models.profile import ProfileModel
from linkedin_ai.utils import enforce_char_limit


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a professional networking AI assistant. You analyze LinkedIn profiles
and generate thoughtful, personalized networking recommendations.

Always respond with valid JSON matching the requested schema exactly.
Be concise, professional, and avoid generic phrases.
Connection notes must be 300 characters or fewer.
Networking scores must be a float from 0.0 to 10.0.
"""

# ── Analysis prompt template ──────────────────────────────────────────────────

ANALYSIS_PROMPT = """Analyze this LinkedIn profile and return a JSON object with these exact keys:

Profile data:
Name: {name}
Headline: {headline}
About: {about}
Company: {company}
Title: {title}
Location: {location}
Skills: {skills}
Topics discussed: {topics}
Recent post themes: {post_themes}
Certifications: {certifications}
Experience count: {exp_count}

Return JSON with these exact keys:
{{
  "summary": "2-3 sentence professional summary",
  "interests": ["list", "of", "3-5", "interests"],
  "networking_score": 7.5,
  "score_rationale": "Brief reason for the score",
  "conversation_starters": ["3 specific conversation starter questions"],
  "connection_note": "Personalized note under 300 chars starting with Hi [name],",
  "follow_up_drafts": ["2 follow-up message drafts for after connecting"],
  "suggested_questions": ["3 thoughtful questions to ask after connecting"]
}}"""


class AIAnalyzer:
    """Wrapper around OpenAI API for profile analysis."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", max_tokens: int = 2048, temperature: float = 0.7) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = OpenAI(api_key=api_key)

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _call_api(self, prompt: str) -> tuple[str, int]:
        """Make an OpenAI API call. Returns (content, tokens_used)."""
        ai_logger.info("API call | model={} | prompt_len={}", self.model, len(prompt))
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        tokens = response.usage.total_tokens if response.usage else 0
        ai_logger.info("API response | tokens={} | content_len={}", tokens, len(content))
        return content, tokens

    def analyze_profile(self, profile: ProfileModel, profile_id: int) -> AnalysisResult:
        """
        Run full AI analysis on a profile.

        Returns an AnalysisResult with all generated content.
        """
        # Build post theme summary
        post_themes = "; ".join([p.text[:100] for p in profile.posts[:3]]) or "No recent posts"

        prompt = ANALYSIS_PROMPT.format(
            name=profile.name,
            headline=profile.headline,
            about=profile.about[:500] if profile.about else "Not provided",
            company=profile.company,
            title=profile.title,
            location=profile.location,
            skills=", ".join(profile.skills[:15]),
            topics=", ".join(profile.topics[:10]),
            post_themes=post_themes,
            certifications=", ".join([c.name for c in profile.certifications[:5]]),
            exp_count=len(profile.experience),
        )

        try:
            raw_content, tokens = self._call_api(prompt)
            data: dict[str, Any] = json.loads(raw_content)
        except (APIError, json.JSONDecodeError) as exc:
            logger.error("AI analysis failed for profile_id={}: {}", profile_id, exc)
            data = {}
            tokens = 0

        # Enforce connection note limit
        note = data.get("connection_note", "")
        note = enforce_char_limit(note, 300)

        result = AnalysisResult(
            profile_id=profile_id,
            profile_url=profile.url,
            profile_name=profile.name,
            summary=data.get("summary", ""),
            interests=data.get("interests", []),
            networking_score=data.get("networking_score", 0.0),
            score_rationale=data.get("score_rationale", ""),
            conversation_starters=data.get("conversation_starters", []),
            connection_note=note,
            follow_up_drafts=data.get("follow_up_drafts", []),
            suggested_questions=data.get("suggested_questions", []),
            ai_model=self.model,
            ai_tokens_used=tokens,
            analyzed_at=datetime.now(timezone.utc),
        )
        logger.info(
            "Analysis complete | profile={} | score={:.1f} | tokens={}",
            profile.name, result.networking_score, tokens,
        )
        return result

    def refine_connection_note(self, profile: ProfileModel, draft: str, user_notes: str = "") -> str:
        """Refine a connection note based on user feedback."""
        prompt = f"""Refine this LinkedIn connection note for {profile.name}.

Current note: {draft}
User feedback: {user_notes or 'Make it more personal and specific.'}
Profile headline: {profile.headline}
Profile topics: {', '.join(profile.topics[:5])}

Return JSON: {{"note": "refined note under 300 chars"}}"""

        try:
            content, _ = self._call_api(prompt)
            data = json.loads(content)
            return enforce_char_limit(data.get("note", draft))
        except Exception as exc:
            logger.error("Note refinement failed: {}", exc)
            return enforce_char_limit(draft)
