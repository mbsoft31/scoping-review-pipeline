"""Models for living systematic reviews.

These Pydantic models describe the configuration of a living review
including its search query, selected databases, update schedule
and optional notification settings.  The scheduler updates the
``next_run`` time after each update and tracks counts of total and
new papers.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class UpdateSchedule(BaseModel):
    """Schedule for periodic updates."""

    frequency: str  # e.g. "daily", "weekly", "monthly"
    next_run: datetime
    last_run: Optional[datetime] = None


class LivingReview(BaseModel):
    """Configuration for a living systematic review."""

    review_id: str
    query: str
    databases: List[str]
    schedule: UpdateSchedule
    screening_criteria: Optional[dict] = None
    notification_email: Optional[str] = None
    created_at: datetime
    last_updated: Optional[datetime] = None
    total_papers: int = 0
    new_papers_since_last: int = 0
    is_active: bool = True