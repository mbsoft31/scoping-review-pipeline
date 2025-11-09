"""High-level API for search queue management.

This provides a simple interface that hides async complexity.
"""

import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import date

from .task_queue import TaskQueue, SearchTask, TaskStatus
from .worker import WorkerPool
from .progress import ProgressTracker
from ..search.orchestrator import SearchOrchestrator
from ..io.cache import SearchCache
from ..core.models import Paper
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SearchQueueManager:
    """Simple high-level API for managing search queues.
    
    Example:
        >>> manager = SearchQueueManager(num_workers=3)
        >>> 
        >>> # Add searches
        >>> task_id1 = manager.add_search("openalex", "machine learning", priority=1)
        >>> task_id2 = manager.add_search("arxiv", "neural networks", priority=2)
        >>> 
        >>> # Run (blocking until done)
        >>> manager.run_all()
        >>> 
        >>> # Get results
        >>> papers = manager.get_results(task_id1)
    """
    
    def __init__(
        self,
        num_workers: int = 3,
        cache_dir: Optional[Path] = None,
        max_retries: int = 3,
    ):
        """Initialize manager.
        
        Args:
            num_workers: Number of concurrent workers (3 is safe default)
            cache_dir: Directory for cache (default: .cache)
            max_retries: Max retry attempts for failed tasks
        """
        self.num_workers = num_workers
        
        # Initialize components
        self.queue = TaskQueue(max_retries=max_retries)
        cache_path = cache_dir or Path(".cache/searches")
        self.cache = SearchCache(cache_path)
        self.orchestrator = SearchOrchestrator(cache_dir=cache_path)
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
        """Add a search task to queue.
        
        Args:
            source: Database name ("openalex", "arxiv", etc.)
            query: Search query string
            start_date: Filter papers from this date
            end_date: Filter papers until this date
            limit: Maximum papers to fetch
            priority: Priority (0=highest, lower numbers run first)
            config: Source-specific configuration
            resume_from_cache: Resume from cached results if available
            
        Returns:
            task_id for tracking this search
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
        
        task_id = self._run_sync(self.queue.enqueue(task))
        
        logger.info(
            f"Added search: {source} query='{query[:50]}...' "
            f"(task_id={task_id[:8]}, priority={priority})"
        )
        
        return task_id
    
    def add_multiple_searches(self, searches: List[Dict[str, Any]]) -> List[str]:
        """Add multiple searches at once.
        
        Args:
            searches: List of search configs (each dict has same keys as add_search)
            
        Returns:
            List of task_ids
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
        """Run all queued searches (BLOCKING until done).
        
        This is the simplest way to use the queue - just call this
        after adding your searches and it handles everything.
        
        Args:
            show_progress: Display live progress updates
            progress_interval: Seconds between progress updates
        """
        logger.info("Starting search queue execution")
        
        async def _run():
            await self.worker_pool.start()
            
            if show_progress:
                await self.progress.watch(interval=progress_interval)
            else:
                await self.worker_pool.wait_until_complete()
            
            await self.worker_pool.stop()
        
        self._run_sync(_run())
        
        if show_progress:
            self.progress.print_summary()
        
        logger.info("Search queue execution completed")
    
    def get_results(self, task_id: str) -> Optional[List[Paper]]:
        """Get results for a completed task.
        
        Args:
            task_id: Task ID from add_search()
            
        Returns:
            List of papers or None if not completed
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
        """Get results from all completed tasks.
        
        Returns:
            Dict mapping task_id -> papers
        """
        results = {}
        for task in self.queue.get_all_tasks():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.CACHED):
                results[task.task_id] = task.papers
        return results
    
    def get_task_status(self, task_id: str) -> Optional[str]:
        """Get current status of a task."""
        task = self.queue.get_task(task_id)
        return task.status.value if task else None
    
    def cancel_task(self, task_id: str):
        """Cancel a task."""
        self._run_sync(self.queue.cancel_task(task_id))
        logger.info(f"Cancelled task {task_id[:8]}")
    
    def get_queue_size(self) -> int:
        """Get number of pending tasks."""
        return self._run_sync(self.queue.size())
    
    def _run_sync(self, coro):
        """Helper to run async code synchronously."""
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop.run_until_complete(coro)
    
    def __enter__(self):
        """Context manager support."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup on exit."""
        if self._loop and not self._loop.is_closed():
            self._loop.close()
        self.cache.close()
