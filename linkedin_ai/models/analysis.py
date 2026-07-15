"""
models/analysis.py — AI analysis result model.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class AnalysisResult(BaseModel):
    """AI-generated analysis for a single LinkedIn profile."""

    profile_id: int
    profile_url: str = ""
    profile_name: str = ""

    # AI outputs
    summary: str = ""
    interests: list[str] = Field(default_factory=list)
    networking_score: float = Field(default=0.0, ge=0.0, le=10.0)
    score_rationale: str = ""
    conversation_starters: list[str] = Field(default_factory=list)
    connection_note: str = ""           # ≤ 300 characters
    follow_up_drafts: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)

    # Metadata
    ai_model: str = "gpt-4o-mini"
    ai_tokens_used: int = 0
    analyzed_at: datetime | None = None

    @field_validator("connection_note", mode="after")
    @classmethod
    def _enforce_note_limit(cls, v: str) -> str:
        return v[:300] if len(v) > 300 else v

    @field_validator("networking_score", mode="before")
    @classmethod
    def _clamp_score(cls, v: object) -> float:
        try:
            val = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(10.0, val))

    @property
    def score_label(self) -> str:
        if self.networking_score >= 8:
            return "Excellent"
        if self.networking_score >= 6:
            return "Good"
        if self.networking_score >= 4:
            return "Fair"
        return "Low"

    @property
    def score_colour(self) -> str:
        """Rich markup colour for the score."""
        if self.networking_score >= 8:
            return "bright_green"
        if self.networking_score >= 6:
            return "green"
        if self.networking_score >= 4:
            return "yellow"
        return "red"

    def to_db_dict(self) -> dict:
        import json
        return {
            "profile_id": self.profile_id,
            "summary": self.summary,
            "interests_json": json.dumps(self.interests),
            "networking_score": self.networking_score,
            "score_rationale": self.score_rationale,
            "starters_json": json.dumps(self.conversation_starters),
            "connection_note": self.connection_note,
            "followup_json": json.dumps(self.follow_up_drafts),
            "questions_json": json.dumps(self.suggested_questions),
            "ai_model": self.ai_model,
            "ai_tokens_used": self.ai_tokens_used,
            "analyzed_at": (self.analyzed_at or datetime.utcnow()).isoformat(),
        }
