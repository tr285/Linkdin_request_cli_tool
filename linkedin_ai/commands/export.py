"""
commands/export.py — `liai export`

Export stored profiles and analyses to CSV, Excel, JSON, or HTML.
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from linkedin_ai.config import get_config
from linkedin_ai.database import Database
from linkedin_ai.exporter import export, ExportFormat

console = Console()
app = typer.Typer(invoke_without_command=True)


@app.callback(invoke_without_command=True)
def export_data(
    fmt: str = typer.Option("csv", "--format", "-f", help="Export format: csv|excel|json|html|all"),
    output_dir: Path = typer.Option(Path("reports"), "--output", "-o", help="Output directory"),
    status: str = typer.Option("", "--status", "-s", help="Filter by status (approved|analyzed|skipped|new)"),
) -> None:
    """
    Export profiles and AI analyses to files.

    Supported formats: csv, excel, json, html, all
    """
    cfg = get_config()
    db = Database(cfg.database_path)
    out_dir = output_dir or cfg.export_dir

    valid_formats = {"csv", "excel", "json", "html", "all"}
    if fmt not in valid_formats:
        console.print(f"[red]Invalid format '{fmt}'. Choose from: {', '.join(sorted(valid_formats))}[/red]")
        raise typer.Exit(1)

    status_filter = status or None

    with console.status(f"[cyan]Generating {fmt.upper()} export…[/cyan]"):
        paths = export(
            db=db,
            fmt=fmt,  # type: ignore[arg-type]
            output_dir=out_dir,
            status_filter=status_filter,
        )

    if not paths:
        console.print("[yellow]No data available for export. Run search + analyze first.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Exported Files", border_style="green")
    table.add_column("Format", style="bold cyan", width=8)
    table.add_column("File", style="white")
    table.add_column("Size", justify="right", style="dim")

    for p in paths:
        size = p.stat().st_size if p.exists() else 0
        size_str = f"{size / 1024:.1f} KB" if size > 1024 else f"{size} B"
        table.add_row(p.suffix.lstrip(".").upper(), str(p), size_str)

    console.print(table)
    console.print(f"\n✅  [green]{len(paths)} file(s) exported to[/green] [bold]{out_dir}[/bold]")
