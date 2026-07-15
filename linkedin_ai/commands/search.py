"""
commands/search.py — `liai search`

Interactive filter prompts → LinkedIn people search → store in DB.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from linkedin_ai.browser import BrowserManager
from linkedin_ai.cache import Cache
from linkedin_ai.config import get_config
from linkedin_ai.database import Database
from linkedin_ai.models.search import SearchFilter
from linkedin_ai.search import search_profiles

console = Console()
app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def search(
    keywords: str = typer.Option("", "--keywords", "-k", help="Search keywords"),
    title: str = typer.Option("", "--title", "-t", help="Job title filter"),
    company: str = typer.Option("", "--company", "-co", help="Company filter"),
    industry: str = typer.Option("", "--industry", "-i", help="Industry filter"),
    country: str = typer.Option("", "--country", help="Country filter"),
    city: str = typer.Option("", "--city", help="City filter"),
    skills: str = typer.Option("", "--skills", "-s", help="Comma-separated skills"),
    experience: str = typer.Option("any", "--experience", "-e", help="Experience level: entry|associate|mid-senior|director|executive|any"),
    max_results: int = typer.Option(25, "--max", "-m", help="Maximum results to fetch"),
    interactive: bool = typer.Option(False, "--interactive", "-I", help="Launch interactive filter prompts"),
) -> None:
    """
    Search LinkedIn for people matching your filters.

    Results are stored in the local database for analysis.
    """
    cfg = get_config()

    # Interactive mode — prompt for each filter
    if interactive or not any([keywords, title, company, industry]):
        console.print(Panel(
            "[bold cyan]Interactive Search Filters[/bold cyan]\n"
            "[dim]Press ENTER to skip any filter[/dim]",
            border_style="cyan",
        ))
        keywords = Prompt.ask("[cyan]Keywords[/cyan]", default=keywords or "")
        title = Prompt.ask("[cyan]Job Title[/cyan]", default=title or "")
        company = Prompt.ask("[cyan]Company[/cyan]", default=company or "")
        industry = Prompt.ask("[cyan]Industry[/cyan]", default=industry or "")
        country = Prompt.ask("[cyan]Country[/cyan]", default=country or "")
        city = Prompt.ask("[cyan]City[/cyan]", default=city or "")
        skills = Prompt.ask("[cyan]Skills (comma-separated)[/cyan]", default=skills or "")
        experience = Prompt.ask(
            "[cyan]Experience Level[/cyan]",
            choices=["entry", "associate", "mid-senior", "director", "executive", "any"],
            default=experience,
        )
        max_results = int(Prompt.ask("[cyan]Max results[/cyan]", default=str(max_results)))

    filters = SearchFilter(
        keywords=keywords,
        title=title,
        company=company,
        industry=industry,
        country=country,
        city=city,
        skills=skills,
        experience_level=experience,  # type: ignore[arg-type]
        max_results=max_results,
    )

    console.print(Panel(
        f"[bold]Search filters:[/bold]\n{filters.summary()}",
        title="🔍 LinkedIn People Search",
        border_style="blue",
    ))

    db = Database(cfg.database_path)
    cache = Cache(cfg.cache_dir, cfg.cache_ttl_hours)
    manager = BrowserManager(cookies_path=cfg.cookies_path, headless=cfg.headless)

    async def _run() -> list[int]:
        async with manager:
            return await search_profiles(manager, filters, db, cache, cfg.rate_limit_delay)

    with console.status("[cyan]Searching LinkedIn…[/cyan]"):
        profile_ids = asyncio.run(_run())

    if not profile_ids:
        console.print("[yellow]No profiles found. Try different filters.[/yellow]")
        raise typer.Exit(0)

    # Display results table
    table = Table(title=f"Found {len(profile_ids)} profiles", border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="bold white")
    table.add_column("Headline", style="cyan", max_width=50)
    table.add_column("URL", style="blue dim", max_width=40)

    for i, pid in enumerate(profile_ids[:20], 1):
        row = db.get_profile(pid)
        if row:
            table.add_row(
                str(i),
                row.get("name") or "—",
                row.get("headline") or "—",
                row.get("url") or "—",
            )

    console.print(table)

    if len(profile_ids) > 20:
        console.print(f"[dim]… and {len(profile_ids) - 20} more in the database[/dim]")

    console.print(f"\n✅  [green]{len(profile_ids)} profiles stored.[/green] "
                  "Run [bold]liai analyze[/bold] to generate AI insights.")
