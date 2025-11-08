"""Living review scheduler and models.

This package manages the configuration and execution of living
systematic reviews.  A living review automatically reruns searches at
user‑configured intervals, deduplicates new records, performs
automated screening and notifies reviewers of updates.
"""

from .models import LivingReview, UpdateSchedule  # noqa: F401
from .scheduler import LivingReviewScheduler  # noqa: F401