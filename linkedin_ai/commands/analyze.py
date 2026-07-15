"""
commands/analyze.py — `liai analyze`

Runs AI analysis on stored profiles and saves results to DB.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from linkedin_ai.ai import AIAnalyzer
from linkedin_ai.analyzer import ProfileAnalyzer
from linkedin_ai.config import get_config
from linkedin_ai.database import Database

console = Console()
app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def analyze(
    profile_id: int = typer.Option(0, "--id", help="Analyze a specific profile by ID"),
    status: str = typer.Option("new", "--status", "-s", help="Analyze profiles with this status: new|all"),
    limit: int = typer.Option(50, "--limit", "-l", help="Max profiles to analyze"),
    reanalyze: bool = typer.Option(False, "--reanalyze", "-r", help="Re-analyze already-analyzed profiles"),
    min_score: float = typer.Option(0.0, "--min-score", help="Only show results above this score"),
) -> None:
    """
    Run AI analysis on stored LinkedIn profiles.

    Generates professional summaries, networking scores,
    connection notes, and conversation starters.
    """
    cfg = get_config()

    if not cfg.has_openai_key:
        console.print(Panel(
            "[red bold]OpenAI API key not configured.[/red bold]\n\n"
            "Set it with:\n"
            "  [bold]export OPENAI_API_KEY=sk-...[/bold]\n"
            "or add it to your [bold].env[/bold] file.",
            title="❌ Missing API Key",
            border_style="red",
        ))
        raise typer.Exit(1)

    db = Database(cfg.database_path)
    ai = AIAnalyzer(
        api_key=cfg.openai_api_key,
        model=cfg.openai_model,
        max_tokens=cfg.openai_max_tokens,
        temperature=cfg.openai_temperature,
    )
    analyzer = ProfileAnalyzer(db, ai)

    if profile_id:
        # Single profile analysis
        console.print(f"[cyan]Analyzing profile id={profile_id}…[/cyan]")
        result = analyzer.analyze_one(profile_id)
        if not result:
            console.print(f"[red]Profile id={profile_id} not found.[/red]")
            raise typer.Exit(1)

        console.print(Panel(
            f"[bold]{result.profile_name}[/bold]\n\n"
            f"[dim]Score:[/dim] [{result.score_colour}]{result.networking_score:.1f}/10 — {result.score_label}[/{result.score_colour}]\n\n"
            f"[dim]Summary:[/dim]\n{result.summary}\n\n"
            f"[dim]Connection Note:[/dim]\n[italic]{result.connection_note}[/italic]\n\n"
            f"[dim]Starters:[/dim]\n" + "\n".join(f"  • {s}" for s in result.conversation_starters),
            title="🤖 AI Analysis Result",
            border_style="green",
        ))
        return

    # Batch analysis
    filter_status = None if status == "all" else status
    profiles = db.list_profiles(status=filter_status, limit=limit)

    if not profiles:
        console.print(f"[yellow]No profiles with status='{filter_status}' found.[/yellow]")
        raise typer.Exit(0)

    console.print(Panel(
        f"[bold cyan]Analyzing {len(profiles)} profiles[/bold cyan]\n"
        f"Model: [bold]{cfg.openai_model}[/bold] | Skip existing: [bold]{not reanalyze}[/bold]",
        title="🤖 Batch AI Analysis",
        border_style="cyan",
    ))

    profile_ids = [p["id"] for p in profiles]
    results = analyzer.analyze_batch(profile_ids, skip_existing=not reanalyze)

    if not results:
        console.print("[yellow]No new profiles were analyzed.[/yellow]")
        return

    # Results summary table
    table = Table(title="Analysis Results", border_style="green")
    table.add_column("Name", style="bold white")
    table.add_column("Score", justify="center", width=10)
    table.add_column("Label", width=10)
    table.add_column("Connection Note Preview", max_width=55, style="italic dim")

    for r in sorted(results, key=lambda x: x.networking_score, reverse=True):
        if r.networking_score >= min_score:
            score_str = f"[{r.score_colour}]{r.networking_score:.1f}[/{r.score_colour}]"
            table.add_row(
                r.profile_name or "—",
                score_str,
                r.score_label,
                (r.connection_note[:55] + "…") if len(r.connection_note) > 55 else r.connection_note,
            )

    console.print(table)

    stats = analyzer.compute_aggregate_stats()
    console.print(
        f"\n✅  [green]{len(results)} profiles analyzed[/green] | "
        f"Avg score: [bold]{stats.get('avg_score', 0):.2f}[/bold] | "
        f"Best: [bold green]{stats.get('max_score', 0):.2f}[/bold green]\n"
        "Run [bold]liai preview[/bold] to review and approve profiles."
    )
