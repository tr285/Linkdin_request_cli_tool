"""
commands/version.py — `liai version`

Display version, Python, and dependency information.
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console
from rich.table import Table

from linkedin_ai import __version__

console = Console()
app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def version(ctx: typer.Context) -> None:
    """Show liai version and dependency information."""
    if ctx.invoked_subcommand is not None:
        return

    deps = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("pydantic", "pydantic"),
        ("playwright", "playwright"),
        ("pandas", "pandas"),
        ("openai", "openai"),
        ("loguru", "loguru"),
        ("tenacity", "tenacity"),
        ("jinja2", "jinja2"),
        ("openpyxl", "openpyxl"),
    ]

    table = Table(title="📦 liai Package Information", border_style="cyan")
    table.add_column("Package", style="bold cyan")
    table.add_column("Version", style="white")
    table.add_column("Status", justify="center")

    table.add_row("liai", __version__, "[green]✓[/green]")
    table.add_row(
        "Python",
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "[green]✓[/green]" if sys.version_info >= (3, 12) else "[yellow]⚠[/yellow]",
    )

    for display, module in deps:
        try:
            pkg = __import__(module)
            ver = getattr(pkg, "__version__", getattr(pkg, "VERSION", "unknown"))
            status = "[green]✓[/green]"
        except ImportError:
            ver = "not installed"
            status = "[red]✗[/red]"
        table.add_row(display, str(ver), status)

    console.print(table)
    console.print(
        f"\n[dim]liai v{__version__} — LinkedIn AI Networking Assistant\n"
        "https://github.com/your-org/linkedin-ai-cli[/dim]"
    )
