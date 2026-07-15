"""
cli.py — Root Typer application.

Registers all sub-commands and initialises logging on startup.
Entry point: `liai` (defined in pyproject.toml)
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from linkedin_ai import __version__
from linkedin_ai.config import get_config
from linkedin_ai.logger import setup_logging

# ── Import command modules ────────────────────────────────────────────────────
from linkedin_ai.commands import login as _login_mod
from linkedin_ai.commands import search as _search_mod
from linkedin_ai.commands import analyze as _analyze_mod
from linkedin_ai.commands import preview as _preview_mod
from linkedin_ai.commands import open as _open_mod
from linkedin_ai.commands import export as _export_mod
from linkedin_ai.commands import report as _report_mod
from linkedin_ai.commands import config as _config_mod
from linkedin_ai.commands import version as _version_mod
from linkedin_ai.commands import doctor as _doctor_mod

console = Console()

# ── Root app ──────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="liai",
    help=(
        "[bold cyan]liai[/bold cyan] — LinkedIn AI Networking Assistant\n\n"
        "An AI-powered CLI to find relevant professionals, analyse their profiles,\n"
        "generate personalised connection notes, and organise your outreach.\n\n"
        "[dim]Workflow:[/dim]  [bold]liai login[/bold] → [bold]liai search[/bold] → "
        "[bold]liai analyze[/bold] → [bold]liai preview[/bold] → [bold]liai export[/bold]"
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=True,
)


@app.callback()
def _startup(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug logging", is_eager=False),
    log_dir: Path = typer.Option(Path("logs"), "--log-dir", hidden=True),
) -> None:
    """Global startup: initialise logging and ensure directories exist."""
    if ctx.invoked_subcommand == "version":
        return
    try:
        cfg = get_config()
        cfg.ensure_dirs()
        setup_logging(
            log_dir=cfg.log_dir,
            log_level="DEBUG" if debug else cfg.log_level,
            debug=debug,
        )
    except Exception:
        # Don't crash startup if config fails
        setup_logging(log_dir=log_dir, log_level="INFO")


# ── Register sub-commands ─────────────────────────────────────────────────────

app.add_typer(_login_mod.app,   name="login",   help="🔐 Authenticate with LinkedIn via browser")
app.add_typer(_search_mod.app,  name="search",  help="🔍 Search LinkedIn people with filters")
app.add_typer(_analyze_mod.app, name="analyze", help="🤖 AI-analyze stored profiles")
app.add_typer(_preview_mod.app, name="preview", help="👀 Interactively review and approve profiles")
app.add_typer(_open_mod.app,    name="open",    help="🔗 Open a profile in your browser")
app.add_typer(_export_mod.app,  name="export",  help="📤 Export data to CSV/Excel/JSON/HTML")
app.add_typer(_report_mod.app,  name="report",  help="📊 Display summary report in terminal")
app.add_typer(_config_mod.app,  name="config",  help="⚙️  View / update configuration")
app.add_typer(_version_mod.app, name="version", help="📦 Show version information")
app.add_typer(_doctor_mod.app,  name="doctor",  help="🩺 Run environment diagnostics")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
