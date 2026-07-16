"""
commands/login.py — `liai login`

Opens LinkedIn in Playwright browser and guides user through manual login.
Saves session cookies for reuse.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from linkedin_ai.auth import import_cookies_from_file, login_flow, verify_session
from linkedin_ai.browser import BrowserManager
from linkedin_ai.config import get_config

console = Console()
app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def login(
    check: bool = typer.Option(False, "--check", "-c", help="Only verify existing session"),
    import_cookies: str = typer.Option(
        "", "--import-cookies",
        help="Path to a cookies JSON file exported from your browser (skips browser login)",
    ),
) -> None:
    """
    Authenticate with LinkedIn via your browser.

    Opens a browser window and auto-detects when you've logged in.
    No credentials are stored — only session cookies.

    Alternatively, export your LinkedIn cookies with the 'Cookie-Editor'
    browser extension and use --import-cookies <file.json>.
    """
    cfg = get_config()

    # ── Cookie import shortcut ──────────────────────────────────────────────
    if import_cookies:
        src = Path(import_cookies)
        if not src.exists():
            console.print(f"[red]File not found: {src}[/red]")
            raise typer.Exit(1)
        try:
            count = import_cookies_from_file(src, cfg.cookies_path)
            console.print(Panel(
                f"✅  [green]Imported {count} cookies![/green]\n"
                "Run [bold]liai login --check[/bold] to verify the session.",
                title="🔐 Cookies Imported",
                border_style="green",
            ))
        except Exception as exc:
            console.print(f"[red]Failed to import cookies: {exc}[/red]")
            raise typer.Exit(1)
        return

    # ── Session check ───────────────────────────────────────────────────────
    if check:
        console.print("[cyan]Checking existing LinkedIn session…[/]")
        manager = BrowserManager(
            cookies_path=cfg.cookies_path,
            headless=True,
        )

        async def _check() -> bool:
            async with manager:
                return await verify_session(manager)

        valid = asyncio.run(_check())
        if valid:
            console.print(Panel("✅  [green]Session is valid![/green]", title="Session Status"))
        else:
            console.print(Panel(
                "❌  [red]Session expired or no cookies found.[/red]\n"
                "Run [bold]liai login[/bold] to authenticate.",
                title="Session Status",
            ))
        raise typer.Exit(0 if valid else 1)

    # ── Full browser login ──────────────────────────────────────────────────
    console.print(Panel(
        "[bold cyan]LinkedIn Login[/bold cyan]\n\n"
        "A browser window will open. Log into LinkedIn — [bold]the session saves automatically[/bold].\n\n"
        "[dim]• No credentials are stored by liai\n"
        "• Only session cookies are saved to disk\n"
        f"• Cookies path: {cfg.cookies_path}[/dim]\n\n"
        "[yellow]Alternative:[/yellow] Export cookies via the [bold]Cookie-Editor[/bold] browser extension "
        "and run [bold]liai login --import-cookies cookies.json[/bold]",
        title="🔐 Authentication",
        border_style="cyan",
    ))

    manager = BrowserManager(
        cookies_path=cfg.cookies_path,
        headless=False,  # Always show browser for login
    )

    async def _login() -> bool:
        async with manager:
            return await login_flow(manager)

    success = asyncio.run(_login())

    if success:
        console.print(Panel(
            "✅  [green]Login successful![/green] Session saved.\n"
            "You can now run [bold]liai search[/bold] to find profiles.",
            border_style="green",
        ))
    else:
        console.print("[red]Login failed. Please try again.[/red]")
        raise typer.Exit(1)
