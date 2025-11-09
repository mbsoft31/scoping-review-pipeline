"""High-level API for search queue management."""

import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import date

from .task_queue import TaskQueue, SearchTask, TaskStatus
from .worker import WorkerPool
from .progress import ProgressTracker
from ..search.orchestrator import SearchOrchestrator
from ..search.strategy import SearchStrategy
from ..io.cache import SearchCache
from ..core.models import Paper
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SearchQueueManager:
    """
    Simple high-level API for managing search queues.
    
    This class provides an easy-to-use interface that hides all async
    complexity. You don't need to understand async/await - just use
    this API to add searches and run them.
    
    Features:
    - Simple synchronous API (no async/await needed)
    - Automatic worker pool management
    - Cache integration
    - Progress tracking
    - Graceful error handling
    - Context manager support
    
    Example:
        >>> manager = SearchQueueManager(num_workers=3)
        >>> 
        >>> # Add searches
        >>> task1 = manager.add_search("openalex", "machine learning", limit=100)
        >>> task2 = manager.add_search("arxiv", "neural networks", limit=50)
        >>> 
        >>> # Run (blocking until done)
        >>> manager.run_all()
        >>> 
        >>> # Get results
        >>> papers1 = manager.get_results(task1)
        >>> papers2 = manager.get_results(task2)
    
    Context Manager:
        >>> with SearchQueueManager(num_workers=3) as manager:
        ...     manager.add_search("openalex", "AI", limit=100)
        ...     manager.run_all()
        ...     results = manager.get_all_results()
    """
    
    def __init__(
        self,
        num_workers: int = 3,
        cache_dir: Optional[Path] = None,
        strategy: Optional[SearchStrategy] = None,
    ):
        """
        Initialize manager.
        
        Args:
            num_workers: Number of concurrent workers (default: 3)
                        Higher = faster but more API load
                        Safe range: 2-5 workers
            cache_dir: Directory for cache (default: .cache)
            strategy: Search strategy (default: SearchStrategy.default_strategy())
        """
        self.num_workers = num_workers
        
        # Initialize components
        self.queue = TaskQueue()
        self.cache = SearchCache(cache_dir or Path(".cache/searches"))
        self.orchestrator = SearchOrchestrator(
            cache_dir=cache_dir,
            strategy=strategy
        )
        self.worker_pool = WorkerPool(
            queue=self.queue,
            orchestrator=self.orchestrator,
            cache=self.cache,
            num_workers=num_workers,
        )
        self.progress = ProgressTracker(self.queue)
        
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        logger.info(
            f"SearchQueueManager initialized with {num_workers} workers"
        )
    
    def add_search(
        self,
        source: str,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
        priority: int = 0,
        config: Optional[Dict[str, Any]] = None,
        resume_from_cache: bool = True,
    ) -> str:
        """
        Add a search task to queue.
        
        Args:
            source: Database name ("openalex", "arxiv", "crossref", "semantic_scholar")
            query: Search query string
            start_date: Filter papers from this date (inclusive)
            end_date: Filter papers until this date (inclusive)
            limit: Maximum papers to fetch (None = unlimited)
            priority: Execution priority (0=highest, lower numbers run first)
            config: Source-specific configuration dict
            resume_from_cache: Resume from cached results if available
            
        Returns:
            task_id: Unique ID for tracking this search
            
        Example:
            >>> manager = SearchQueueManager()
            >>> task_id = manager.add_search(
            ...     source="openalex",
            ...     query="machine learning fairness",
            ...     start_date=date(2020, 1, 1),
            ...     limit=500,
            ...     priority=1
            ... )
        """
        task = SearchTask(
            source=source,
            query=query,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            priority=priority,
            config=config or {},
            resume_from_cache=resume_from_cache,
        )
        
        # Register with cache
        task.cache_query_id = self.cache.register_query(
            source=source,
            query=query,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )
        
        # Enqueue (use run_sync helper)
        task_id = self._run_sync(self.queue.enqueue(task))
        
        logger.info(
            f"Added search: {source} query='{query[:50]}...' "
            f"(task_id={task_id[:8]}, priority={priority})"
        )
        
        return task_id
    
    def add_multiple_searches(
        self,
        searches: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Add multiple searches at once.
        
        Args:
            searches: List of search configs (each dict has same keys as add_search)
            
        Returns:
            List of task_ids
            
        Example:
            >>> manager = SearchQueueManager()
            >>> searches = [
            ...     {"source": "openalex", "query": "AI", "limit": 100, "priority": 1},
            ...     {"source": "arxiv", "query": "ML", "limit": 50, "priority": 2},
            ... ]
            >>> task_ids = manager.add_multiple_searches(searches)
        """
        task_ids = []
        for search in searches:
            task_id = self.add_search(**search)
            task_ids.append(task_id)
        
        logger.info(f"Added {len(searches)} searches to queue")
        return task_ids
    
    def run_all(
        self,
        show_progress: bool = True,
        progress_interval: float = 2.0
    ):
        """
        Run all queued searches (BLOCKING until done).
        
        This is the simplest way to use the queue - just call this
        after adding your searches and it handles everything.
        
        The method will:
        1. Start worker pool
        2. Execute all queued tasks
        3. Show live progress (if show_progress=True)
        4. Stop workers when done
        5. Print final summary
        
        Args:
            show_progress: Display live progress updates (default: True)
            progress_interval: Seconds between progress updates (default: 2.0)
            
        Example:
            >>> manager = SearchQueueManager(num_workers=3)
            >>> manager.add_search("openalex", "AI", limit=100)
            >>> manager.add_search("arxiv", "ML", limit=50)
            >>> manager.run_all()  # Blocks until both complete
        """
        logger.info("Starting search queue execution")
        
        async def _run():
            # Start workers
            await self.worker_pool.start()
            
            # Watch progress
            if show_progress:
                await self.progress.watch(interval=progress_interval)
            else:
                await self.worker_pool.wait_until_complete()
            
            # Stop workers
            await self.worker_pool.stop()
        
        # Run event loop
        self._run_sync(_run())
        
        # Print final summary
        self.progress.print_summary()
        
        logger.info("Search queue execution completed")
    
    def get_results(self, task_id: str) -> Optional[List[Paper]]:
        """
        Get results for a completed task.
        
        Args:
            task_id: Task ID from add_search()
            
        Returns:
            List of papers or None if not completed
            
        Example:
            >>> task_id = manager.add_search("openalex", "AI", limit=100)
            >>> manager.run_all()
            >>> papers = manager.get_results(task_id)
            >>> print(f"Found {len(papers)} papers")
        """
        task = self.queue.get_task(task_id)
        if not task:
            logger.warning(f"Task {task_id[:8]} not found")
            return None
        
        if task.status not in (TaskStatus.COMPLETED, TaskStatus.CACHED):
            logger.warning(
                f"Task {task_id[:8]} not completed (status={task.status.value})"
            )
            return None
        
        return task.papers
    
    def get_all_results(self) -> Dict[str, List[Paper]]:
        """
        Get results from all completed tasks.
        
        Returns:
            Dict mapping task_id -> papers
            
        Example:
            >>> manager.add_search("openalex", "AI", limit=100)
            >>> manager.add_search("arxiv", "ML", limit=50)
            >>> manager.run_all()
            >>> all_results = manager.get_all_results()
            >>> total = sum(len(p) for p in all_results.values())
            >>> print(f"Total papers: {total}")
        """
        results = {}
        for task in self.queue.get_all_tasks():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.CACHED):
                results[task.task_id] = task.papers
        return results
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """
        Get current status of a task.
        
        Args:
            task_id: Task ID to check
            
        Returns:
            Status string ("pending", "running", "completed", "failed", "cached", "cancelled")
            or None if task not found
        """
        task = self.queue.get_task(task_id)
        return task.status.value if task else None
    
    def cancel_task(self, task_id: str):
        """
        Cancel a task.
        
        Args:
            task_id: Task ID to cancel
            
        Example:
            >>> task_id = manager.add_search("openalex", "AI", limit=1000)
            >>> # Changed mind
            >>> manager.cancel_task(task_id)
        """
        self._run_sync(self.queue.cancel_task(task_id))
        logger.info(f"Cancelled task {task_id[:8]}")
    
    def get_queue_size(self) -> int:
        """
        Get number of pending tasks.
        
        Returns:
            Number of tasks waiting to execute
        """
        return self._run_sync(self.queue.size())
    
    def _run_sync(self, coro):
        """
        Helper to run async code synchronously.
        
        This is the magic that lets you use the async queue without
        understanding async/await!
        """
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coro)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        if self._loop and not self._loop.is_closed():
            self._loop.close()
        self.cache.close()
