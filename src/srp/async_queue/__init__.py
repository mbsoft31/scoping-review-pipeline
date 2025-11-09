"""
Async task queue system for managing concurrent searches.

This module provides a complete task queue infrastructure that handles:
- Priority-based task execution
- Intelligent error handling with circuit breakers
- Automatic retry with adaptive backoff
- Cache integration and resumption
- Real-time progress tracking
- Concurrent worker pool management
- Batch processing for multiple queries/sources

The main entry point is SearchQueueManager which provides a simple API
that doesn't require understanding async/await internals.

Basic Usage:
    >>> from srp.async_queue import SearchQueueManager
    >>> 
    >>> manager = SearchQueueManager(num_workers=3)
    >>> task_id = manager.add_search("openalex", "machine learning", limit=100)
    >>> manager.run_all()  # Blocks until done
    >>> papers = manager.get_results(task_id)

Batch Processing:
    >>> from srp.async_queue import BatchProcessor
    >>> 
    >>> batch = BatchProcessor(num_workers=5)
    >>> papers = batch.search_multiple_queries(
    ...     source="openalex",
    ...     queries=["AI fairness", "ML bias", "algorithmic equity"],
    ...     limit=500
    ... )

Error Handling:
    The queue system automatically handles:
    - Rate limiting (429 errors) with exponential backoff
    - Network errors with retry
    - API errors with intelligent retry strategies
    - Circuit breakers to prevent cascading failures

Advanced Usage:
    See examples/queue/ for more patterns.
"""

from .task_queue import TaskQueue, SearchTask, TaskStatus
from .worker import WorkerPool, Worker
from .progress import ProgressTracker, QueueStats
from .manager import SearchQueueManager
from .error_handler import ErrorHandler, ErrorType, CircuitBreaker, CircuitState
from .batch import BatchProcessor, search_multiple_queries, search_across_sources

__all__ = [
    # Core queue components
    "TaskQueue",
    "SearchTask",
    "TaskStatus",
    "WorkerPool",
    "Worker",
    "ProgressTracker",
    "QueueStats",
    
    # High-level APIs
    "SearchQueueManager",
    "BatchProcessor",
    
    # Error handling
    "ErrorHandler",
    "ErrorType",
    "CircuitBreaker",
    "CircuitState",
    
    # Convenience functions
    "search_multiple_queries",
    "search_across_sources",
]

__version__ = "0.2.0"
