"""Scheduler for maintaining living systematic reviews.

This module implements a simple scheduler that can register living
reviews, periodically run updates by rerunning searches, deduplicate
new papers and optionally screen them.  It also supports sending
notification emails when new papers are found.  Scheduling is
implemented using the ``schedule`` library and runs in the main
event loop.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import schedule

from ..dedup.deduplicator import Deduplicator  # noqa: F401
from ..search.orchestrator import SearchOrchestrator
from ..screening.screener import AutoScreener  # noqa: F401
from ..utils.logging import get_logger
from .models import LivingReview, UpdateSchedule

logger = get_logger(__name__)


class LivingReviewScheduler:
    """Manage periodic updates for registered living reviews."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.active_reviews: Dict[str, LivingReview] = {}

    def register_living_review(
        self,
        review_id: str,
        query: str,
        databases: List[str],
        schedule_type: str = "weekly",
        screening_criteria: Optional[dict] = None,
        notification_email: Optional[str] = None,
    ) -> LivingReview:
        """Register a new living review and persist its configuration."""
        review = LivingReview(
            review_id=review_id,
            query=query,
            databases=databases,
            schedule=UpdateSchedule(
                frequency=schedule_type,
                next_run=self._calculate_next_run(schedule_type),
            ),
            screening_criteria=screening_criteria,
            notification_email=notification_email,
            created_at=datetime.utcnow(),
        )
        self.active_reviews[review_id] = review
        self._save_review(review)
        logger.info(f"Registered living review: {review_id}")
        return review

    def _calculate_next_run(self, schedule_type: str) -> datetime:
        """Compute the next run time based on the frequency."""
        now = datetime.utcnow()
        if schedule_type == "daily":
            return now + timedelta(days=1)
        if schedule_type == "weekly":
            return now + timedelta(weeks=1)
        if schedule_type == "monthly":
            return now + timedelta(days=30)
        return now + timedelta(days=7)

    async def run_update(self, review_id: str) -> Dict:
        """Perform an update for a given living review."""
        if review_id not in self.active_reviews:
            raise ValueError(f"Review {review_id} not found")
        review = self.active_reviews[review_id]
        logger.info(f"Running update for review {review_id}")
        orchestrator = SearchOrchestrator()
        start_date = review.last_updated.date() if review.last_updated else None
        new_papers = []
        for db in review.databases:
            papers = await orchestrator.search_source(
                source=db,
                query=review.query,
                start_date=start_date,
                limit=None,
            )
            new_papers.extend(papers)
        orchestrator.close()
        logger.info(f"Found {len(new_papers)} new papers for {review_id}")
        # Placeholder: deduplicate and screen new papers here
        # Update review metadata
        review.last_updated = datetime.utcnow()
        review.new_papers_since_last = len(new_papers)
        review.total_papers += len(new_papers)
        review.schedule.next_run = self._calculate_next_run(review.schedule.frequency)
        self._save_review(review)
        # Placeholder: send notifications
        return {
            "review_id": review_id,
            "new_papers": len(new_papers),
            "total_papers": review.total_papers,
            "next_update": review.schedule.next_run.isoformat(),
        }

    def _save_review(self, review: LivingReview) -> None:
        """Persist the living review configuration to disk."""
        review_file = self.data_dir / f"{review.review_id}.json"
        review_file.write_text(review.model_dump_json(indent=2))

    async def _send_notification(self, review: LivingReview, new_count: int) -> None:
        """Send an update notification to the configured email address."""
        # Integrate with an email API such as SendGrid here.  This is a stub.
        logger.info(
            f"Notification: {new_count} new papers found for living review {review.review_id}"
        )

    def start_scheduler(self) -> None:
        """Start the scheduler loop in a blocking manner."""
        logger.info("Starting living review scheduler")
        schedule.every(1).hours.do(self._check_and_run_updates)
        while True:
            schedule.run_pending()
            time.sleep(60)

    def _check_and_run_updates(self) -> None:
        """Check whether any living reviews are due for an update and run them."""
        now = datetime.utcnow()
        for review_id, review in list(self.active_reviews.items()):
            if review.is_active and review.schedule.next_run <= now:
                logger.info(f"Triggering scheduled update for {review_id}")
                asyncio.run(self.run_update(review_id))