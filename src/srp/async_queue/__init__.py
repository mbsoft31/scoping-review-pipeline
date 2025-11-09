"""
Async task queue system for managing concurrent searches.

This module provides a complete task queue infrastructure that handles:
- Priority-based task execution
- Automatic retry logic
- Cache integration and resumption
- Real-time progress tracking
- Concurrent worker pool management

The main entry point is SearchQueueManager which provides a simple API
that doesn't require understanding async/await internals.

Basic Usage:
    >>> from srp.async_queue import SearchQueueManager
    >>> 
    >>> manager = SearchQueueManager(num_workers=3)
    >>> task_id = manager.add_search("openalex", "machine learning", limit=100)
    >>> manager.run_all()  # Blocks until done
    >>> papers = manager.get_results(task_id)

Advanced Usage:
    See examples/queue_usage_examples.py for more patterns.
"""

from .task_queue import TaskQueue, SearchTask, TaskStatus
from .worker import WorkerPool, Worker
from .progress import ProgressTracker, QueueStats
from .manager import SearchQueueManager

__all__ = [
    "TaskQueue",
    "SearchTask",
    "TaskStatus",
    "WorkerPool",
    "Worker",
    "ProgressTracker",
    "QueueStats",
    "SearchQueueManager",
]

__version__ = "0.1.0"
