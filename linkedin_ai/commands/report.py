"""
commands/report.py — `liai report`

Display a Rich summary report in the terminal.
"""

from __future__ import annotations

from collections import Counter

import typer
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from linkedin_ai.analyzer import ProfileAnalyzer
from linkedin_ai.ai import AIAnalyzer
from linkedin_ai.config import get_config
from linkedin_ai.database import Database

console = Console()
app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def report(
    top: int = typer.Option(10, "--top", "-t", help="Show top N profiles"),
    min_score: float = typer.Option(0.0, "--min-score", help="Minimum networking score"),
) -> None:
    """
    Display a summary report of analyzed profiles.

    Shows top profiles by networking score, industry breakdown,
    company distribution, and aggregate statistics.
    """
    cfg = get_config()
    db = Database(cfg.database_path)

    total_profiles = db.count_profiles()
    analyzed_profiles = db.count_profiles("analyzed")
    approved_profiles = db.count_profiles("approved")
    skipped_profiles = db.count_profiles("skipped")

    if total_profiles == 0:
        console.print("[yellow]No profiles in database. Run [bold]liai search[/bold] first.[/yellow]")
        raise typer.Exit(0)

    # ── Overview stats ────────────────────────────────────────────────────────
    stats_panel = Panel(
        f"[bold white]Total Profiles:[/bold white]   {total_profiles}\n"
        f"[bold cyan]Analyzed:[/bold cyan]         {analyzed_profiles}\n"
        f"[bold green]Approved:[/bold green]         {approved_profiles}\n"
        f"[bold red]Skipped:[/bold red]          {skipped_profiles}",
        title="📊 Database Overview",
        border_style="cyan",
        width=35,
    )

    # ── Score distribution ────────────────────────────────────────────────────
    rows = db.list_analyses_with_profiles(limit=1000)
    scores = [float(r.get("networking_score") or 0) for r in rows]

    if scores:
        avg = sum(scores) / len(scores)
        dist = {"Excellent (8-10)": 0, "Good (6-8)": 0, "Fair (4-6)": 0, "Low (0-4)": 0}
        for s in scores:
            if s >= 8:
                dist["Excellent (8-10)"] += 1
            elif s >= 6:
                dist["Good (6-8)"] += 1
            elif s >= 4:
                dist["Fair (4-6)"] += 1
            else:
                dist["Low (0-4)"] += 1

        score_text = f"[bold]Avg Score:[/bold] [cyan]{avg:.2f}[/cyan]\n\n"
        colours = {"Excellent (8-10)": "bright_green", "Good (6-8)": "green", "Fair (4-6)": "yellow", "Low (0-4)": "red"}
        for label, count in dist.items():
            bar = "█" * int(count / max(scores) * 20) if count else ""
            score_text += f"[{colours[label]}]{label:18s}[/{colours[label]}] {bar} {count}\n"

        score_panel = Panel(score_text, title="🎯 Score Distribution", border_style="blue", width=45)
        console.print(Columns([stats_panel, score_panel]))
    else:
        console.print(stats_panel)

    # ── Top profiles table ────────────────────────────────────────────────────
    top_rows = sorted(rows, key=lambda r: r.get("networking_score") or 0, reverse=True)
    top_rows = [r for r in top_rows if (r.get("networking_score") or 0) >= min_score][:top]

    if top_rows:
        top_table = Table(title=f"🏆 Top {len(top_rows)} Profiles by Score", border_style="green")
        top_table.add_column("#", style="dim", width=4)
        top_table.add_column("Name", style="bold white")
        top_table.add_column("Company", style="cyan")
        top_table.add_column("Title", style="cyan dim")
        top_table.add_column("Score", justify="center", width=8)
        top_table.add_column("Status", width=10)

        for i, r in enumerate(top_rows, 1):
            score = r.get("networking_score") or 0
            if score >= 8:
                colour = "bright_green"
            elif score >= 6:
                colour = "green"
            elif score >= 4:
                colour = "yellow"
            else:
                colour = "red"
            top_table.add_row(
                str(i),
                r.get("name") or "—",
                r.get("company") or "—",
                r.get("title") or "—",
                f"[{colour}]{score:.1f}[/{colour}]",
                r.get("status") or "new",
            )
        console.print(top_table)

    # ── Company + Skills breakdown ────────────────────────────────────────────
    import json as _json
    all_profiles = db.list_profiles(limit=1000)
    companies = Counter([r.get("company") or "Unknown" for r in all_profiles if r.get("company")])
    all_skills: list[str] = []
    for r in all_profiles:
        all_skills.extend(_json.loads(r.get("skills_json") or "[]"))
    top_skills = Counter(all_skills).most_common(10)

    if companies:
        comp_table = Table(title="🏢 Top Companies", border_style="blue", width=40)
        comp_table.add_column("Company", style="cyan")
        comp_table.add_column("Profiles", justify="right", style="white")
        for company, count in companies.most_common(8):
            comp_table.add_row(company, str(count))

        skill_table = Table(title="🛠 Top Skills", border_style="magenta", width=40)
        skill_table.add_column("Skill", style="magenta")
        skill_table.add_column("Count", justify="right", style="white")
        for skill, count in top_skills:
            skill_table.add_row(skill, str(count))

        console.print(Columns([comp_table, skill_table]))

    # ── Recent report runs ────────────────────────────────────────────────────
    runs = db.list_report_runs(limit=5)
    if runs:
        run_table = Table(title="📁 Recent Exports", border_style="dim", width=70)
        run_table.add_column("Format", style="bold", width=8)
        run_table.add_column("Rows", justify="right", width=6)
        run_table.add_column("Path", style="dim")
        run_table.add_column("Created", style="dim", width=22)
        for run in runs:
            run_table.add_row(
                run.get("format", "?").upper(),
                str(run.get("row_count") or 0),
                run.get("path") or "—",
                run.get("created_at") or "—",
            )
        console.print(run_table)

    console.print(
        "\nRun [bold]liai export --format all[/bold] to generate reports  |  "
        "[bold]liai preview[/bold] to review profiles"
    )
