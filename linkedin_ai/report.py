"""
report.py — Multi-format report generation.

Generates CSV, Excel, JSON, and HTML reports from a list of ReportRow objects.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from linkedin_ai.models.report import ReportRow
from linkedin_ai.utils import now_iso, slugify


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rows_to_df(rows: list[ReportRow]) -> pd.DataFrame:
    return pd.DataFrame([r.model_dump() for r in rows])


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# ── CSV ───────────────────────────────────────────────────────────────────────

def generate_csv(rows: list[ReportRow], output_path: Path) -> Path:
    _ensure_dir(output_path)
    df = _rows_to_df(rows)
    df.to_csv(output_path, index=False, encoding="utf-8")
    logger.info("CSV report written: {} ({} rows)", output_path, len(rows))
    return output_path


# ── Excel ─────────────────────────────────────────────────────────────────────

def generate_excel(rows: list[ReportRow], output_path: Path) -> Path:
    _ensure_dir(output_path)
    df = _rows_to_df(rows)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Profiles")
        ws = writer.sheets["Profiles"]

        # Auto-size columns
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 50)

        # Freeze header row
        ws.freeze_panes = "A2"

    logger.info("Excel report written: {} ({} rows)", output_path, len(rows))
    return output_path


# ── JSON ──────────────────────────────────────────────────────────────────────

def generate_json(rows: list[ReportRow], output_path: Path) -> Path:
    _ensure_dir(output_path)
    data = {
        "generated_at": now_iso(),
        "total_profiles": len(rows),
        "profiles": [r.model_dump() for r in rows],
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("JSON report written: {} ({} rows)", output_path, len(rows))
    return output_path


# ── HTML ──────────────────────────────────────────────────────────────────────

def generate_html(
    rows: list[ReportRow],
    output_path: Path,
    template_dir: str | Path | None = None,
) -> Path:
    _ensure_dir(output_path)

    if template_dir and Path(template_dir).exists():
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
        )
        template = env.get_template("report.html.jinja2")
    else:
        # Inline fallback template
        template_str = _INLINE_HTML_TEMPLATE
        env = Environment(autoescape=select_autoescape(["html"]))
        template = env.from_string(template_str)

    html = template.render(
        rows=rows,
        generated_at=now_iso(),
        total=len(rows),
    )
    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML report written: {} ({} rows)", output_path, len(rows))
    return output_path


# ── Inline HTML template (fallback) ──────────────────────────────────────────

_INLINE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>liai — LinkedIn Networking Report</title>
<style>
  :root { --bg: #0f172a; --surface: #1e293b; --accent: #6366f1; --text: #e2e8f0; --muted: #94a3b8; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', system-ui, sans-serif; padding: 2rem; }
  h1 { color: var(--accent); font-size: 1.8rem; margin-bottom: 0.5rem; }
  .meta { color: var(--muted); font-size: 0.85rem; margin-bottom: 2rem; }
  table { width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 12px; overflow: hidden; }
  th { background: var(--accent); color: #fff; padding: 0.75rem 1rem; text-align: left; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
  td { padding: 0.65rem 1rem; border-bottom: 1px solid #334155; font-size: 0.85rem; vertical-align: top; }
  tr:hover td { background: #263045; }
  .score { font-weight: 700; font-size: 1rem; }
  .score-high { color: #34d399; }
  .score-mid { color: #fbbf24; }
  .score-low { color: #f87171; }
  .note { font-style: italic; color: var(--muted); max-width: 300px; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>
<h1>🤝 LinkedIn AI Networking Report</h1>
<p class="meta">Generated: {{ generated_at }} &nbsp;|&nbsp; Total profiles: {{ total }}</p>
<table>
  <thead>
    <tr>
      <th>#</th><th>Name</th><th>Title / Company</th><th>Skills</th>
      <th>Score</th><th>Connection Note</th><th>Status</th>
    </tr>
  </thead>
  <tbody>
  {% for row in rows %}
  {% set sc = row.networking_score %}
  <tr>
    <td>{{ loop.index }}</td>
    <td><a href="{{ row.url }}" target="_blank">{{ row.name or '—' }}</a><br>
        <small style="color:var(--muted)">{{ row.location }}</small></td>
    <td>{{ row.title or '—' }}<br><small style="color:var(--muted)">{{ row.company }}</small></td>
    <td><small>{{ row.skills[:80] }}</small></td>
    <td class="score {% if sc >= 8 %}score-high{% elif sc >= 5 %}score-mid{% else %}score-low{% endif %}">
        {{ "%.1f"|format(sc) }}<br><small>{{ row.score_label }}</small></td>
    <td class="note">{{ row.connection_note or '—' }}</td>
    <td><span style="text-transform:capitalize">{{ row.status }}</span></td>
  </tr>
  {% endfor %}
  </tbody>
</table>
</body>
</html>"""
