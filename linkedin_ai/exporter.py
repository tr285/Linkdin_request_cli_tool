"""
exporter.py — Export orchestration.

Queries the database, builds ReportRow objects via pandas,
and delegates to the appropriate report generator.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from linkedin_ai.database import Database
from linkedin_ai.models.report import ReportRow
from linkedin_ai import report as report_gen
from linkedin_ai.utils import now_iso, slugify

ExportFormat = Literal["csv", "excel", "json", "html", "all"]


def _build_report_rows(db: Database, status: str | None = None) -> list[ReportRow]:
    """Query DB and build ReportRow list."""
    rows_data = db.list_analyses_with_profiles(limit=1000)

    if status:
        rows_data = [r for r in rows_data if r.get("status") == status]

    report_rows: list[ReportRow] = []
    for row in rows_data:
        skills = json.loads(row.get("skills_json") or "[]")
        topics = json.loads(row.get("topics_json") or "[]")
        interests = json.loads(row.get("interests_json") or "[]") if "interests_json" in row else []
        starters = json.loads(row.get("starters_json") or "[]") if "starters_json" in row else []
        experience = json.loads(row.get("experience_json") or "[]")
        posts = json.loads(row.get("posts_json") or "[]")

        score = float(row.get("networking_score") or 0.0)
        if score >= 8:
            label = "Excellent"
        elif score >= 6:
            label = "Good"
        elif score >= 4:
            label = "Fair"
        else:
            label = "Low"

        report_rows.append(ReportRow(
            profile_id=row.get("id") or 0,
            name=row.get("name") or "",
            url=row.get("url") or "",
            headline=row.get("headline") or "",
            company=row.get("company") or "",
            title=row.get("title") or "",
            location=row.get("location") or "",
            industry=row.get("industry") or "",
            skills=", ".join(skills[:10]),
            experience_count=len(experience),
            post_count=len(posts),
            topics=", ".join(topics[:8]),
            status=row.get("status") or "new",
            networking_score=score,
            score_label=label,
            summary=row.get("summary") or "",
            interests=", ".join(interests[:5]),
            connection_note=row.get("connection_note") or "",
            conversation_starters=starters[0] if starters else "",
            analyzed_at=row.get("analyzed_at") or "",
            scraped_at=row.get("scraped_at") or "",
        ))

    return report_rows


def export(
    db: Database,
    fmt: ExportFormat = "csv",
    output_dir: Path = Path("reports"),
    status_filter: str | None = None,
    template_dir: Path | None = None,
) -> list[Path]:
    """
    Export profiles + analyses to the requested format(s).

    Returns list of output file paths.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = _build_report_rows(db, status=status_filter)

    if not rows:
        logger.warning("No data to export (status_filter={})", status_filter)
        return []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = output_dir / f"liai_report_{timestamp}"
    generated: list[Path] = []

    def _do_export(f: str) -> None:
        if f == "csv":
            p = report_gen.generate_csv(rows, base.with_suffix(".csv"))
        elif f == "excel":
            p = report_gen.generate_excel(rows, base.with_suffix(".xlsx"))
        elif f == "json":
            p = report_gen.generate_json(rows, base.with_suffix(".json"))
        elif f == "html":
            p = report_gen.generate_html(rows, base.with_suffix(".html"), template_dir)
        else:
            return
        generated.append(p)
        db.save_report_run(f, str(p), len(rows))

    if fmt == "all":
        for f in ["csv", "excel", "json", "html"]:
            _do_export(f)
    else:
        _do_export(fmt)

    logger.info("Export complete: {} file(s) generated", len(generated))
    return generated
