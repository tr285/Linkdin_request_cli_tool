"""
messaging.py — Connection note and follow-up message management.

Handles template rendering, character-limit enforcement,
and AI-powered note refinement.
"""

from __future__ import annotations

from linkedin_ai.models.analysis import AnalysisResult
from linkedin_ai.models.profile import ProfileModel
from linkedin_ai.utils import enforce_char_limit


# ── Default note templates ────────────────────────────────────────────────────

TEMPLATES = {
    "professional": (
        "Hi {first_name}, I came across your profile and was impressed by your work "
        "in {field}. I'd love to connect and exchange insights. Looking forward to it!"
    ),
    "mutual_interest": (
        "Hi {first_name}, your experience in {field} resonates with me. "
        "I work on similar challenges and think we could have a great conversation. "
        "Would love to connect!"
    ),
    "peer": (
        "Hi {first_name}, as a fellow {title}, I find your perspective on {topic} "
        "really valuable. Would love to connect and learn from each other."
    ),
}


def get_first_name(name: str) -> str:
    """Extract first name from full name."""
    return name.split()[0] if name else "there"


def render_template(
    template_key: str,
    profile: ProfileModel,
    topic: str = "",
) -> str:
    """Render a note template with profile data."""
    tpl = TEMPLATES.get(template_key, TEMPLATES["professional"])
    first_name = get_first_name(profile.name)
    field = profile.industry or profile.company or profile.title or "your field"
    title = profile.title or "professional"

    note = tpl.format(
        first_name=first_name,
        field=field,
        title=title,
        topic=topic or (profile.topics[0] if profile.topics else "the industry"),
    )
    return enforce_char_limit(note, 300)


def format_note_preview(analysis: AnalysisResult, profile: ProfileModel) -> str:
    """Return a formatted note with character count."""
    note = analysis.connection_note
    char_count = len(note)
    status = "✓" if char_count <= 300 else "✗ EXCEEDS LIMIT"
    return f"{note}\n\n[{char_count}/300 chars {status}]"


def get_follow_up_message(analysis: AnalysisResult, index: int = 0) -> str:
    """Get a follow-up message draft by index."""
    drafts = analysis.follow_up_drafts
    if not drafts:
        return (
            f"Hi {get_first_name(analysis.profile_name)}, "
            "great to connect! I'd love to hear more about your work. "
            "Would you be open to a quick call?"
        )
    return drafts[index % len(drafts)]


def edit_note_interactively(current_note: str) -> str:
    """Prompt the user to edit a note in the terminal."""
    print(f"\nCurrent note ({len(current_note)}/300 chars):")
    print("─" * 50)
    print(current_note)
    print("─" * 50)
    print("Enter your edited note (or press ENTER to keep current):")
    new_note = input().strip()
    if not new_note:
        return current_note
    return enforce_char_limit(new_note, 300)
