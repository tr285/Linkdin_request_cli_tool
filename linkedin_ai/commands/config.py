"""
commands/config.py — `liai config`

View and modify application settings stored in SQLite.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from linkedin_ai.config import get_config
from linkedin_ai.database import Database
from linkedin_ai.settings import Settings, SETTINGS_SCHEMA

console = Console()
app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def config_cmd(
    show: bool = typer.Option(False, "--show", "-s", help="Show all current settings"),
    key: str = typer.Option("", "--set", "-k", help="Setting key to update"),
    value: str = typer.Option("", "--value", "-v", help="New value for the setting"),
    reset: str = typer.Option("", "--reset", "-r", help="Reset a setting to its default"),
) -> None:
    """
    View or modify liai configuration settings.

    Examples:
        liai config --show
        liai config --set openai_model --value gpt-4o
        liai config --reset theme
    """
    cfg = get_config()
    db = Database(cfg.database_path)
    settings = Settings(db)

    if key and value:
        if key not in SETTINGS_SCHEMA:
            console.print(f"[red]Unknown setting: '{key}'[/red]")
            console.print(f"Valid keys: {', '.join(SETTINGS_SCHEMA.keys())}")
            raise typer.Exit(1)
        settings.set(key, value)
        console.print(f"✅  [green]Updated:[/green] [bold]{key}[/bold] = [cyan]{value}[/cyan]")
        return

    if reset:
        if reset not in SETTINGS_SCHEMA:
            console.print(f"[red]Unknown setting: '{reset}'[/red]")
            raise typer.Exit(1)
        settings.reset(reset)
        console.print(f"♻️  [yellow]Reset:[/yellow] [bold]{reset}[/bold] to default")
        return

    # Default: show all settings
    table = Table(title="⚙️  liai Configuration", border_style="cyan")
    table.add_column("Key", style="bold cyan", width=22)
    table.add_column("Current Value", style="white", width=20)
    table.add_column("Default", style="dim", width=15)
    table.add_column("Description", style="dim")
    table.add_column("Choices", style="dim", width=30)

    for row in settings.list_all():
        current = str(settings.get(row["key"]))
        is_default = current == str(SETTINGS_SCHEMA[row["key"]]["default"])
        value_style = "dim" if is_default else "bold green"
        table.add_row(
            row["key"],
            f"[{value_style}]{current}[/{value_style}]",
            row["default"],
            row["description"],
            row["choices"] or "—",
        )

    console.print(table)

    # Show env-level config
    console.print(Panel(
        f"[dim]OpenAI Key:[/dim]  {'[green]✓ Set[/green]' if cfg.has_openai_key else '[red]✗ Not set[/red]'}\n"
        f"[dim]Model:[/dim]      [cyan]{cfg.openai_model}[/cyan]\n"
        f"[dim]Database:[/dim]   {cfg.database_path}\n"
        f"[dim]Cache:[/dim]      {cfg.cache_dir}\n"
        f"[dim]Exports:[/dim]    {cfg.export_dir}\n"
        f"[dim]Logs:[/dim]       {cfg.log_dir}",
        title="🔧 Environment Config (.env)",
        border_style="blue",
    ))

    console.print(
        "\nUpdate with: [bold]liai config --set <key> --value <value>[/bold]\n"
        "Or set [bold]OPENAI_API_KEY[/bold] in your .env file"
    )
