"""
analyzer.py — Profile data aggregation and scoring logic.

Combines scraped profile data with AI analysis to produce
enriched AnalysisResult objects and persist them to the database.
"""

from __future__ import annotations

from loguru import logger
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from linkedin_ai.ai import AIAnalyzer
from linkedin_ai.database import Database
from linkedin_ai.models.analysis import AnalysisResult
from linkedin_ai.models.profile import ProfileModel


class ProfileAnalyzer:
    """Orchestrates AI analysis for a batch of profiles."""

    def __init__(self, db: Database, ai: AIAnalyzer) -> None:
        self.db = db
        self.ai = ai

    def analyze_one(self, profile_id: int) -> AnalysisResult | None:
        """Analyze a single profile by its database ID."""
        row = self.db.get_profile(profile_id)
        if not row:
            logger.warning("Profile id={} not found in database", profile_id)
            return None

        profile = ProfileModel.from_db_dict(row)
        logger.info("Analyzing profile: {} ({})", profile.display_name, profile.url)

        result = self.ai.analyze_profile(profile, profile_id)

        # Persist analysis to DB
        self.db.save_analysis(result.to_db_dict())
        self.db.update_profile_status(profile_id, "analyzed")

        return result

    def analyze_batch(
        self,
        profile_ids: list[int],
        skip_existing: bool = True,
    ) -> list[AnalysisResult]:
        """
        Analyze multiple profiles with a Rich progress bar.

        Args:
            profile_ids: List of profile row IDs to analyze.
            skip_existing: If True, skip profiles that already have an analysis.

        Returns:
            List of AnalysisResult objects (successes only).
        """
        results: list[AnalysisResult] = []

        # Filter already-analyzed if requested
        if skip_existing:
            todo = [
                pid for pid in profile_ids
                if self.db.get_analysis(pid) is None
            ]
            skipped = len(profile_ids) - len(todo)
            if skipped:
                logger.info("Skipping {} already-analyzed profiles", skipped)
        else:
            todo = list(profile_ids)

        if not todo:
            logger.info("All profiles already analyzed")
            return results

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
        ) as progress:
            task = progress.add_task(
                f"[cyan]Analyzing {len(todo)} profiles…", total=len(todo)
            )
            for pid in todo:
                result = self.analyze_one(pid)
                if result:
                    results.append(result)
                progress.advance(task)

        logger.info(
            "Batch analysis complete: {}/{} profiles analyzed",
            len(results), len(todo),
        )
        return results

    def get_top_profiles(self, limit: int = 10, min_score: float = 0.0) -> list[dict]:
        """Return top profiles by networking score."""
        rows = self.db.list_analyses_with_profiles(limit=100)
        filtered = [
            r for r in rows
            if (r.get("networking_score") or 0) >= min_score
        ]
        return sorted(
            filtered,
            key=lambda r: r.get("networking_score") or 0,
            reverse=True,
        )[:limit]

    def compute_aggregate_stats(self) -> dict:
        """Compute summary statistics across all analyzed profiles."""
        rows = self.db.list_analyses_with_profiles(limit=1000)
        if not rows:
            return {}

        scores = [r.get("networking_score") or 0.0 for r in rows]
        companies = [r.get("company") or "Unknown" for r in rows]

        from collections import Counter
        top_companies = Counter(companies).most_common(5)

        return {
            "total_analyzed": len(rows),
            "avg_score": round(sum(scores) / len(scores), 2),
            "max_score": round(max(scores), 2),
            "min_score": round(min(scores), 2),
            "top_companies": top_companies,
        }
