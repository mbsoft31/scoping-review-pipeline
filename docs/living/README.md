# Living Reviews Module

The **living** module enables the creation of *living systematic reviews*—reviews that are continuously updated as new evidence becomes available.  It handles scheduling of searches, deduplication, automatic screening and notifications.

## Models

[`models.py`](../../src/srp/living/models.py) defines:

- `UpdateSchedule`: Specifies the update frequency (`daily`, `weekly`, `monthly`), the time of the next scheduled run and the last run time.
- `LivingReview`: Captures the configuration and state of a living review, including the search query, target databases, update schedule, screening criteria, notification email, creation and update timestamps, and counts of total papers and new papers since the last update.

## Scheduler

The `LivingReviewScheduler` class in [`scheduler.py`](../../src/srp/living/scheduler.py) orchestrates periodic updates:

- **Register a review** – `register_living_review()` saves a review configuration to disk and schedules the next run based on the specified frequency.  Each review is identified by a unique `review_id`.
- **Calculate next run** – `_calculate_next_run()` determines the next update time relative to the current UTC time.
- **Run updates** – `run_update(review_id)` performs a single update: it calls the `SearchOrchestrator` to fetch new papers since the last update, deduplicates them against the existing corpus and optionally performs auto screening if criteria are provided.  Counts of new papers are updated, and a notification can be sent via email (integrate via SendGrid or similar).  The schedule is then advanced.
- **Scheduler loop** – `start_scheduler()` uses the [`schedule`](https://schedule.readthedocs.io/) package to run `run_update()` at regular intervals (every hour) and checks whether any reviews require updating.

The living module stores review configurations as JSON files under the specified data directory (`data_dir`), making it easy to reload and resume scheduled tasks.

## Extending

To integrate living reviews into your workflow, call `LivingReviewScheduler.register_living_review()` programmatically or via a CLI command (not yet exposed).  Extend `_send_notification()` to hook into your preferred notification service (e.g. SendGrid, Slack webhook).  For persistent storage across sessions, ensure that the data directory is mounted to a durable location.