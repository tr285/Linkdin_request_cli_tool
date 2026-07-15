"""
tests/test_database.py — Unit tests for the Database class.
"""

from __future__ import annotations

import json

import pytest

from linkedin_ai.database import Database
from linkedin_ai.models.profile import ProfileModel


class TestDatabaseSchema:
    def test_schema_creates_all_tables(self, tmp_db: Database) -> None:
        with tmp_db._conn() as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert "profiles" in tables
        assert "searches" in tables
        assert "analyses" in tables
        assert "report_runs" in tables
        assert "settings" in tables

    def test_wal_mode_enabled(self, tmp_db: Database) -> None:
        with tmp_db._conn() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"


class TestProfileCRUD:
    def test_upsert_and_get_profile(self, tmp_db: Database) -> None:
        data = {
            "url": "https://linkedin.com/in/testuser",
            "name": "Test User",
            "headline": "Engineer at ACME",
        }
        profile_id = tmp_db.upsert_profile(data)
        assert profile_id > 0

        row = tmp_db.get_profile(profile_id)
        assert row is not None
        assert row["name"] == "Test User"
        assert row["url"] == "https://linkedin.com/in/testuser"

    def test_upsert_updates_existing(self, tmp_db: Database) -> None:
        url = "https://linkedin.com/in/testuser"
        tmp_db.upsert_profile({"url": url, "name": "Old Name"})
        tmp_db.upsert_profile({"url": url, "name": "New Name"})

        row = tmp_db.get_profile_by_url(url)
        assert row is not None
        assert row["name"] == "New Name"

    def test_update_profile_status(self, tmp_db: Database) -> None:
        pid = tmp_db.upsert_profile({"url": "https://linkedin.com/in/u1", "name": "U1"})
        tmp_db.update_profile_status(pid, "approved")
        row = tmp_db.get_profile(pid)
        assert row is not None
        assert row["status"] == "approved"

    def test_list_profiles_filter_by_status(self, tmp_db: Database) -> None:
        tmp_db.upsert_profile({"url": "https://linkedin.com/in/u1", "name": "U1", "status": "new"})
        tmp_db.upsert_profile({"url": "https://linkedin.com/in/u2", "name": "U2"})
        pid2 = tmp_db.upsert_profile({"url": "https://linkedin.com/in/u3", "name": "U3"})
        tmp_db.update_profile_status(pid2, "analyzed")

        analyzed = tmp_db.list_profiles(status="analyzed")
        assert len(analyzed) == 1
        assert analyzed[0]["name"] == "U3"

    def test_count_profiles(self, tmp_db: Database) -> None:
        tmp_db.upsert_profile({"url": "https://linkedin.com/in/u1"})
        tmp_db.upsert_profile({"url": "https://linkedin.com/in/u2"})
        assert tmp_db.count_profiles() == 2


class TestSearchCRUD:
    def test_save_and_list_searches(self, tmp_db: Database) -> None:
        search_id = tmp_db.save_search({"title": "Engineer"}, result_count=5)
        assert search_id > 0

        searches = tmp_db.list_searches()
        assert len(searches) == 1
        assert searches[0]["result_count"] == 5

    def test_link_search_result(self, tmp_db: Database) -> None:
        search_id = tmp_db.save_search({}, result_count=1)
        pid = tmp_db.upsert_profile({"url": "https://linkedin.com/in/u1"})
        tmp_db.link_search_result(search_id, pid)  # Should not raise


class TestAnalysisCRUD:
    def test_save_and_get_analysis(self, tmp_db: Database) -> None:
        pid = tmp_db.upsert_profile({"url": "https://linkedin.com/in/u1", "name": "User"})
        tmp_db.save_analysis({
            "profile_id": pid,
            "summary": "Great engineer",
            "networking_score": 8.5,
            "connection_note": "Hi there!",
        })
        analysis = tmp_db.get_analysis(pid)
        assert analysis is not None
        assert analysis["networking_score"] == 8.5
        assert analysis["connection_note"] == "Hi there!"

    def test_analysis_upsert(self, tmp_db: Database) -> None:
        pid = tmp_db.upsert_profile({"url": "https://linkedin.com/in/u1"})
        tmp_db.save_analysis({"profile_id": pid, "networking_score": 5.0})
        tmp_db.save_analysis({"profile_id": pid, "networking_score": 9.0})
        analysis = tmp_db.get_analysis(pid)
        assert analysis is not None
        assert analysis["networking_score"] == 9.0


class TestSettingsCRUD:
    def test_get_set_setting(self, tmp_db: Database) -> None:
        tmp_db.set_setting("theme", "light")
        assert tmp_db.get_setting("theme") == "light"

    def test_get_setting_default(self, tmp_db: Database) -> None:
        assert tmp_db.get_setting("nonexistent_key", "fallback") == "fallback"

    def test_list_settings(self, tmp_db: Database) -> None:
        tmp_db.set_setting("k1", "v1")
        tmp_db.set_setting("k2", "v2")
        all_settings = tmp_db.list_settings()
        assert all_settings["k1"] == "v1"
        assert all_settings["k2"] == "v2"
