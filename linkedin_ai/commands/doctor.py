"""
commands/doctor.py — `liai doctor`

Environment health check: Python version, API key, browser,
database, dependencies, directories.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from linkedin_ai.config import get_config

console = Console()
app = typer.Typer()

CHECK = "[green]✓[/green]"
WARN  = "[yellow]⚠[/yellow]"
FAIL  = "[red]✗[/red]"


def _check(condition: bool, ok_msg: str, fail_msg: str) -> tuple[str, str]:
    return (CHECK, ok_msg) if condition else (FAIL, fail_msg)


@app.callback(invoke_without_command=True)
def doctor(ctx: typer.Context) -> None:
    """
    Run environment diagnostics.

    Checks Python version, OpenAI key, Playwright browser,
    database, cache, and all required dependencies.
    """
    if ctx.invoked_subcommand is not None:
        return

    cfg = get_config()
    cfg.ensure_dirs()

    table = Table(title="🩺 liai Doctor — Environment Diagnostics", border_style="cyan")
    table.add_column("Check", style="bold white", width=28)
    table.add_column("Status", justify="center", width=6)
    table.add_column("Detail", style="dim")

    issues: list[str] = []

    # ── Python version ────────────────────────────────────────────────────────
    py_ok = sys.version_info >= (3, 12)
    status, detail = _check(
        py_ok,
        f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        f"Python 3.12+ required (found {sys.version_info.major}.{sys.version_info.minor})",
    )
    table.add_row("Python Version", status, detail)
    if not py_ok:
        issues.append("Upgrade to Python 3.12+")

    # ── OpenAI API key ────────────────────────────────────────────────────────
    status, detail = _check(
        cfg.has_openai_key,
        f"Key set (model: {cfg.openai_model})",
        "OPENAI_API_KEY not set or invalid format",
    )
    table.add_row("OpenAI API Key", status, detail)
    if not cfg.has_openai_key:
        issues.append("Set OPENAI_API_KEY in .env or environment")

    # ── Dependencies ──────────────────────────────────────────────────────────
    required_pkgs = [
        "typer", "rich", "pydantic", "playwright",
        "pandas", "openai", "loguru", "tenacity", "jinja2", "openpyxl",
    ]
    missing_pkgs = []
    for pkg in required_pkgs:
        try:
            __import__(pkg)
        except ImportError:
            missing_pkgs.append(pkg)

    status, detail = _check(
        not missing_pkgs,
        f"All {len(required_pkgs)} packages installed",
        f"Missing: {', '.join(missing_pkgs)}",
    )
    table.add_row("Python Packages", status, detail)
    if missing_pkgs:
        issues.append(f"Run: pip install {' '.join(missing_pkgs)}")

    # ── Playwright browser ────────────────────────────────────────────────────
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True, text=True, timeout=10,
        )
        browser_ok = "chromium" in result.stdout.lower() or result.returncode == 0
    except Exception:
        browser_ok = False

    # Simpler check: try importing playwright
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        browser_ok = True
        browser_detail = "Playwright installed"
    except ImportError:
        browser_ok = False
        browser_detail = "Playwright not installed"

    status, detail = _check(browser_ok, browser_detail, "Run: playwright install chromium")
    table.add_row("Playwright Browser", status, detail)
    if not browser_ok:
        issues.append("Run: playwright install chromium")

    # ── Database ──────────────────────────────────────────────────────────────
    db_path = cfg.database_path
    db_exists = db_path.exists()
    status, detail = _check(
        db_exists or db_path.parent.exists(),
        f"Database at {db_path}" + (" (exists)" if db_exists else " (will be created)"),
        f"Cannot access {db_path.parent}",
    )
    table.add_row("SQLite Database", status, detail)

    # ── Cookies / session ────────────────────────────────────────────────────
    session_exists = cfg.cookies_path.exists()
    status = CHECK if session_exists else WARN
    detail = (
        f"Session file found ({cfg.cookies_path})"
        if session_exists
        else f"No session — run [bold]liai login[/bold] ({cfg.cookies_path})"
    )
    table.add_row("LinkedIn Session", status, detail)
    if not session_exists:
        issues.append("Run: liai login")

    # ── Directories ───────────────────────────────────────────────────────────
    dirs = {
        "Cache Dir": cfg.cache_dir,
        "Export Dir": cfg.export_dir,
        "Log Dir": cfg.log_dir,
    }
    all_dirs_ok = True
    for label, d in dirs.items():
        ok = d.exists()
        if not ok:
            all_dirs_ok = False
        table.add_row(
            label,
            CHECK if ok else WARN,
            f"{d} ({'exists' if ok else 'will be created'})",
        )

    # ── .env file ────────────────────────────────────────────────────────────
    env_exists = Path(".env").exists()
    status = CHECK if env_exists else WARN
    detail = ".env file found" if env_exists else ".env not found — copy from .env.example"
    table.add_row(".env File", status, detail)
    if not env_exists:
        issues.append("Copy .env.example to .env and fill in your keys")

    console.print(table)

    if issues:
        issues_text = "\n".join(f"  {i+1}. {issue}" for i, issue in enumerate(issues))
        console.print(Panel(
            issues_text,
            title=f"⚠️  {len(issues)} Issue(s) Found",
            border_style="yellow",
        ))
    else:
        console.print(Panel(
            "✅  All checks passed! You're ready to use liai.\n\n"
            "[dim]Next: [bold]liai login[/bold] → [bold]liai search[/bold] → [bold]liai analyze[/bold][/dim]",
            border_style="green",
        ))
