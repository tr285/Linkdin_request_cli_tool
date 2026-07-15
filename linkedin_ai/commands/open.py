"""
commands/open.py — `liai open`

Open a LinkedIn profile in the default system browser.
"""

from __future__ import annotations

import webbrowser

import typer
from rich.console import Console
from rich.panel import Panel

from linkedin_ai.config import get_config
from linkedin_ai.database import Database
from linkedin_ai.utils import is_valid_linkedin_url

console = Console()
app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def open_profile(
    identifier: str = typer.Argument(help="Profile ID (integer) or LinkedIn URL"),
) -> None:
    """
    Open a LinkedIn profile in your default browser.

    Pass either a numeric profile ID from the database
    or a full LinkedIn profile URL.
    """
    cfg = get_config()
    db = Database(cfg.database_path)

    url: str | None = None

    # Check if it's a database ID
    if identifier.isdigit():
        row = db.get_profile(int(identifier))
        if row:
            url = row.get("url")
        if not url:
            console.print(f"[red]Profile id={identifier} not found in database.[/red]")
            raise typer.Exit(1)

    elif is_valid_linkedin_url(identifier):
        url = identifier

    else:
        console.print(
            f"[red]'{identifier}' is not a valid profile ID or LinkedIn URL.[/red]\n"
            "Usage: liai open 42   OR   liai open https://linkedin.com/in/johndoe"
        )
        raise typer.Exit(1)

    console.print(Panel(
        f"[blue]🔗 Opening:[/blue] {url}",
        title="Opening Profile",
        border_style="blue",
    ))
    webbrowser.open(str(url))
