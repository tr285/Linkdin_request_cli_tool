"""
commands/preview.py — `liai preview`

Interactive profile review: approve / edit note / skip / open.
Does NOT send connection requests automatically.
"""

from __future__ import annotations

import json
import webbrowser

import typer
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from linkedin_ai.ai import AIAnalyzer
from linkedin_ai.config import get_config
from linkedin_ai.database import Database
from linkedin_ai.messaging import edit_note_interactively, format_note_preview
from linkedin_ai.models.analysis import AnalysisResult
from linkedin_ai.models.profile import ProfileModel

console = Console()
app = typer.Typer(invoke_without_command=True)


def _render_profile_panel(profile: ProfileModel, analysis: AnalysisResult) -> None:
    """Render a rich profile + analysis display."""
    console.print(Rule(f"[bold cyan]{profile.display_name}[/bold cyan]", style="cyan"))

    # Header info
    info = Table.grid(padding=(0, 2))
    info.add_column(style="dim", width=14)
    info.add_column(style="white")
    info.add_row("Headline:", profile.headline or "—")
    info.add_row("Company:", profile.company or "—")
    info.add_row("Title:", profile.title or "—")
    info.add_row("Location:", profile.location or "—")
    info.add_row("Industry:", profile.industry or "—")
    console.print(info)

    console.print()

    # Score badge
    score_colour = analysis.score_colour
    score_panel = Panel(
        f"[{score_colour}][bold]{analysis.networking_score:.1f}[/bold] / 10[/{score_colour}]\n"
        f"[dim]{analysis.score_label}[/dim]\n\n"
        f"[italic dim]{analysis.score_rationale}[/italic dim]",
        title="🎯 Networking Score",
        border_style=score_colour,
        width=30,
    )

    # Skills
    skills_text = Text()
    for skill in profile.skills[:12]:
        skills_text.append(f"  • {skill}\n", style="cyan")

    skills_panel = Panel(skills_text or "[dim]No skills listed[/dim]", title="🛠 Skills", width=40)
    console.print(Columns([score_panel, skills_panel]))

    # About
    if profile.about:
        console.print(Panel(
            profile.about[:400] + ("…" if len(profile.about) > 400 else ""),
            title="📝 About",
            border_style="blue",
        ))

    # AI Summary
    if analysis.summary:
        console.print(Panel(analysis.summary, title="🤖 AI Summary", border_style="magenta"))

    # Topics
    if profile.topics:
        console.print(Panel(
            "  ".join(f"[cyan]#{t}[/cyan]" for t in profile.topics[:10]),
            title="💬 Topics",
            border_style="blue dim",
        ))

    # Conversation starters
    if analysis.conversation_starters:
        starters_text = "\n".join(f"  [dim]{i+1}.[/dim] {s}" for i, s in enumerate(analysis.conversation_starters))
        console.print(Panel(starters_text, title="💡 Conversation Starters", border_style="yellow"))

    # Connection note
    note_preview = format_note_preview(analysis, profile)
    console.print(Panel(
        note_preview,
        title="✉️  Connection Note",
        border_style="green",
    ))


def _action_prompt() -> str:
    """Show action menu and return user choice."""
    console.print(
        "\n[bold]Actions:[/bold]  "
        "[green][A]pprove[/green]  "
        "[yellow][E]dit note[/yellow]  "
        "[blue][O]pen in browser[/blue]  "
        "[red][S]kip[/red]  "
        "[dim][Q]uit review[/dim]"
    )
    choice = Prompt.ask("Choose", choices=["a", "e", "o", "s", "q"], default="s").lower()
    return choice


@app.callback(invoke_without_command=True)
def preview(
    min_score: float = typer.Option(0.0, "--min-score", "-m", help="Only show profiles above this score"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max profiles to review"),
    status: str = typer.Option("analyzed", "--status", "-s", help="Filter by status"),
) -> None:
    """
    Interactively review AI-analyzed profiles.

    For each profile you can: Approve / Edit note / Open in browser / Skip.
    Connection requests are NEVER sent automatically.
    """
    cfg = get_config()
    db = Database(cfg.database_path)
    ai_client = AIAnalyzer(
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        max_tokens=cfg.openai_max_tokens,
        temperature=cfg.openai_temperature,
    ) if cfg.has_openai_key else None

    rows = db.list_analyses_with_profiles(limit=limit)
    if not rows:
        console.print("[yellow]No analyzed profiles found. Run [bold]liai analyze[/bold] first.[/yellow]")
        raise typer.Exit(0)

    # Filter by score and status
    rows = [
        r for r in rows
        if (r.get("networking_score") or 0) >= min_score
        and (status == "all" or r.get("status") == status)
    ]
    rows.sort(key=lambda r: r.get("networking_score") or 0, reverse=True)

    if not rows:
        console.print(f"[yellow]No profiles match filters (min_score={min_score}, status={status})[/yellow]")
        raise typer.Exit(0)

    console.print(Panel(
        f"[bold cyan]Reviewing {len(rows)} profiles[/bold cyan]  |  "
        f"Min score: [bold]{min_score}[/bold]  |  "
        f"Sorted by score (highest first)",
        title="👀 Profile Preview Mode",
        border_style="cyan",
    ))

    approved = skipped = edited = 0

    for i, row in enumerate(rows, 1):
        console.print(f"\n[dim]Profile {i} of {len(rows)}[/dim]")

        profile = ProfileModel.from_db_dict(row)
        analysis_data = db.get_analysis(row["id"])
        if not analysis_data:
            continue

        analysis = AnalysisResult(
            profile_id=row["id"],
            profile_name=profile.name,
            profile_url=profile.url,
            summary=analysis_data.get("summary") or "",
            interests=json.loads(analysis_data.get("interests_json") or "[]"),
            networking_score=float(analysis_data.get("networking_score") or 0),
            score_rationale=analysis_data.get("score_rationale") or "",
            conversation_starters=json.loads(analysis_data.get("starters_json") or "[]"),
            connection_note=analysis_data.get("connection_note") or "",
            follow_up_drafts=json.loads(analysis_data.get("followup_json") or "[]"),
            suggested_questions=json.loads(analysis_data.get("questions_json") or "[]"),
        )

        _render_profile_panel(profile, analysis)

        action = _action_prompt()

        if action == "a":
            db.update_profile_status(row["id"], "approved")
            console.print("[green]✓ Approved — profile marked for outreach[/green]")
            approved += 1

        elif action == "e":
            new_note = edit_note_interactively(analysis.connection_note)
            # If AI key available, offer AI refinement
            if ai_client and new_note != analysis.connection_note:
                if Prompt.ask("[dim]AI-refine the note?[/dim]", choices=["y", "n"], default="n") == "y":
                    new_note = ai_client.refine_connection_note(profile, new_note)
            # Save updated note
            analysis_data_upd = {**analysis_data, "connection_note": new_note}
            db.save_analysis(analysis_data_upd)
            db.update_profile_status(row["id"], "approved")
            console.print(f"[yellow]✎ Note updated and approved[/yellow]  ({len(new_note)}/300 chars)")
            edited += 1
            approved += 1

        elif action == "o":
            webbrowser.open(profile.url)
            console.print(f"[blue]🔗 Opened {profile.url} in your browser[/blue]")
            # Ask again after opening
            action2 = _action_prompt()
            if action2 == "a":
                db.update_profile_status(row["id"], "approved")
                console.print("[green]✓ Approved[/green]")
                approved += 1
            elif action2 == "s":
                db.update_profile_status(row["id"], "skipped")
                skipped += 1
            elif action2 == "q":
                break

        elif action == "s":
            db.update_profile_status(row["id"], "skipped")
            console.print("[red]↷ Skipped[/red]")
            skipped += 1

        elif action == "q":
            console.print("[dim]Exiting review.[/dim]")
            break

    console.print(Panel(
        f"✅ [green]Approved:[/green] {approved}  |  "
        f"[yellow]Edited:[/yellow] {edited}  |  "
        f"[red]Skipped:[/red] {skipped}\n\n"
        "[dim]Reminder: Connection requests must be sent manually on LinkedIn.[/dim]",
        title="📊 Review Summary",
        border_style="green",
    ))
