"""
database.py — SQLite schema definition and CRUD operations.

All database access goes through the Database class. The schema uses
a single file (default: database/liai.db) with WAL mode for
concurrent read safety.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from loguru import logger

from linkedin_ai.utils import now_iso

# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS profiles (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    url            TEXT NOT NULL UNIQUE,
    linkedin_id    TEXT,
    name           TEXT,
    headline       TEXT,
    about          TEXT,
    company        TEXT,
    title          TEXT,
    location       TEXT,
    country        TEXT,
    industry       TEXT,
    skills_json    TEXT DEFAULT '[]',
    experience_json TEXT DEFAULT '[]',
    posts_json     TEXT DEFAULT '[]',
    certifications_json TEXT DEFAULT '[]',
    topics_json    TEXT DEFAULT '[]',
    post_frequency TEXT,
    status         TEXT DEFAULT 'new',   -- new | analyzed | approved | skipped
    scraped_at     TEXT,
    updated_at     TEXT
);

CREATE TABLE IF NOT EXISTS searches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    filters_json   TEXT NOT NULL,
    result_count   INTEGER DEFAULT 0,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS search_results (
    search_id      INTEGER NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
    profile_id     INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    PRIMARY KEY (search_id, profile_id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id          INTEGER NOT NULL UNIQUE REFERENCES profiles(id) ON DELETE CASCADE,
    summary             TEXT,
    interests_json      TEXT DEFAULT '[]',
    networking_score    REAL DEFAULT 0.0,
    score_rationale     TEXT,
    starters_json       TEXT DEFAULT '[]',
    connection_note     TEXT,
    followup_json       TEXT DEFAULT '[]',
    questions_json      TEXT DEFAULT '[]',
    ai_model            TEXT,
    ai_tokens_used      INTEGER DEFAULT 0,
    analyzed_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    format      TEXT NOT NULL,
    path        TEXT NOT NULL,
    row_count   INTEGER DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_profiles_status ON profiles(status);
CREATE INDEX IF NOT EXISTS idx_profiles_company ON profiles(company);
CREATE INDEX IF NOT EXISTS idx_analyses_score ON analyses(networking_score DESC);
"""


# ── Database class ────────────────────────────────────────────────────────────

class Database:
    """SQLite data access layer. Thread-safe via connection-per-call pattern."""

    def __init__(self, db_path: str | Path = "database/liai.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a connection with row_factory set to Row."""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA_SQL)
        logger.debug("Database schema initialised at {}", self.db_path)

    # ── Profile CRUD ──────────────────────────────────────────────────────────

    def upsert_profile(self, data: dict[str, Any]) -> int:
        """Insert or update a profile. Returns the profile row id."""
        data = {**data, "updated_at": now_iso()}
        sql = """
            INSERT INTO profiles
                (url, linkedin_id, name, headline, about, company, title, location,
                 country, industry, skills_json, experience_json, posts_json,
                 certifications_json, topics_json, post_frequency, status, scraped_at, updated_at)
            VALUES
                (:url, :linkedin_id, :name, :headline, :about, :company, :title, :location,
                 :country, :industry, :skills_json, :experience_json, :posts_json,
                 :certifications_json, :topics_json, :post_frequency, :status, :scraped_at, :updated_at)
            ON CONFLICT(url) DO UPDATE SET
                linkedin_id=excluded.linkedin_id, name=excluded.name,
                headline=excluded.headline, about=excluded.about,
                company=excluded.company, title=excluded.title,
                location=excluded.location, country=excluded.country,
                industry=excluded.industry, skills_json=excluded.skills_json,
                experience_json=excluded.experience_json, posts_json=excluded.posts_json,
                certifications_json=excluded.certifications_json,
                topics_json=excluded.topics_json, post_frequency=excluded.post_frequency,
                updated_at=excluded.updated_at
        """
        defaults: dict[str, Any] = {
            "linkedin_id": None, "name": None, "headline": None, "about": None,
            "company": None, "title": None, "location": None, "country": None,
            "industry": None, "skills_json": "[]", "experience_json": "[]",
            "posts_json": "[]", "certifications_json": "[]", "topics_json": "[]",
            "post_frequency": None, "status": "new", "scraped_at": now_iso(),
        }
        row = {**defaults, **data}
        with self._conn() as conn:
            conn.execute(sql, row)
            profile_id: int = conn.execute(
                "SELECT id FROM profiles WHERE url = ?", (row["url"],)
            ).fetchone()["id"]
        return profile_id

    def get_profile(self, profile_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return dict(row) if row else None

    def get_profile_by_url(self, url: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM profiles WHERE url = ?", (url,)).fetchone()
        return dict(row) if row else None

    def list_profiles(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM profiles"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def update_profile_status(self, profile_id: int, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE profiles SET status = ?, updated_at = ? WHERE id = ?",
                (status, now_iso(), profile_id),
            )

    def count_profiles(self, status: str | None = None) -> int:
        sql = "SELECT COUNT(*) FROM profiles"
        params: list[Any] = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        with self._conn() as conn:
            return conn.execute(sql, params).fetchone()[0]

    # ── Search CRUD ───────────────────────────────────────────────────────────

    def save_search(self, filters: dict[str, Any], result_count: int) -> int:
        sql = "INSERT INTO searches (filters_json, result_count, created_at) VALUES (?, ?, ?)"
        with self._conn() as conn:
            cursor = conn.execute(sql, (json.dumps(filters), result_count, now_iso()))
            return cursor.lastrowid  # type: ignore[return-value]

    def link_search_result(self, search_id: int, profile_id: int) -> None:
        sql = "INSERT OR IGNORE INTO search_results (search_id, profile_id) VALUES (?, ?)"
        with self._conn() as conn:
            conn.execute(sql, (search_id, profile_id))

    def list_searches(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM searches ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Analysis CRUD ─────────────────────────────────────────────────────────

    def save_analysis(self, data: dict[str, Any]) -> int:
        sql = """
            INSERT INTO analyses
                (profile_id, summary, interests_json, networking_score, score_rationale,
                 starters_json, connection_note, followup_json, questions_json,
                 ai_model, ai_tokens_used, analyzed_at)
            VALUES
                (:profile_id, :summary, :interests_json, :networking_score, :score_rationale,
                 :starters_json, :connection_note, :followup_json, :questions_json,
                 :ai_model, :ai_tokens_used, :analyzed_at)
            ON CONFLICT(profile_id) DO UPDATE SET
                summary=excluded.summary, interests_json=excluded.interests_json,
                networking_score=excluded.networking_score, score_rationale=excluded.score_rationale,
                starters_json=excluded.starters_json, connection_note=excluded.connection_note,
                followup_json=excluded.followup_json, questions_json=excluded.questions_json,
                ai_model=excluded.ai_model, ai_tokens_used=excluded.ai_tokens_used,
                analyzed_at=excluded.analyzed_at
        """
        defaults: dict[str, Any] = {
            "summary": "", "interests_json": "[]", "networking_score": 0.0,
            "score_rationale": "", "starters_json": "[]", "connection_note": "",
            "followup_json": "[]", "questions_json": "[]",
            "ai_model": "gpt-4o-mini", "ai_tokens_used": 0,
            "analyzed_at": now_iso(),
        }
        row = {**defaults, **data}
        with self._conn() as conn:
            cursor = conn.execute(sql, row)
            return cursor.lastrowid  # type: ignore[return-value]

    def get_analysis(self, profile_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM analyses WHERE profile_id = ?", (profile_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_analyses_with_profiles(self, limit: int = 100) -> list[dict[str, Any]]:
        sql = """
            SELECT p.*, a.networking_score, a.summary, a.connection_note, a.analyzed_at
            FROM profiles p
            LEFT JOIN analyses a ON a.profile_id = p.id
            WHERE a.id IS NOT NULL
            ORDER BY a.networking_score DESC
            LIMIT ?
        """
        with self._conn() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ── Settings CRUD ─────────────────────────────────────────────────────────

    def get_setting(self, key: str, default: str = "") -> str:
        with self._conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value, now_iso()),
            )

    def list_settings(self) -> dict[str, str]:
        with self._conn() as conn:
            rows = conn.execute("SELECT key, value FROM settings ORDER BY key").fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ── Report runs ───────────────────────────────────────────────────────────

    def save_report_run(self, fmt: str, path: str, row_count: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO report_runs (format, path, row_count, created_at) VALUES (?, ?, ?, ?)",
                (fmt, path, row_count, now_iso()),
            )

    def list_report_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM report_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]
