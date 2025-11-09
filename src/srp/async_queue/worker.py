"""Worker pool for executing search tasks concurrently."""

import asyncio
from typing import Optional
from pathlib import Path

from .task_queue import TaskQueue, SearchTask, TaskStatus
from ..search.orchestrator import SearchOrchestrator
from ..io.cache import SearchCache
from ..utils.logging import get_logger

logger = get_logger(__name__)


class Worker:
    """
    Single worker that processes tasks from queue.
    
    Workers run in an async loop, continuously fetching and executing
    tasks until stopped. Each worker operates independently and handles
    its own error recovery.
    
    Attributes:
        worker_id: Unique worker identifier
        queue: Task queue to pull from
        orchestrator: Search orchestrator for executing searches
        cache: Cache for result persistence
        current_task: Currently executing task
    """
    
    def __init__(
        self,
        worker_id: int,
        queue: TaskQueue,
        orchestrator: SearchOrchestrator,
        cache: SearchCache,
    ):
        """
        Initialize worker.
        
        Args:
            worker_id: Unique identifier for this worker
            queue: TaskQueue to pull tasks from
            orchestrator: SearchOrchestrator for executing searches
            cache: SearchCache for result persistence
        """
        self.worker_id = worker_id
        self.queue = queue
        self.orchestrator = orchestrator
        self.cache = cache
        self.current_task: Optional[SearchTask] = None
        self._stop_event = asyncio.Event()
    
    async def run(self):
        """Worker main loop."""
        logger.info(f"Worker {self.worker_id} started")
        
        while not self._stop_event.is_set():
            try:
                # Get next task (with timeout for responsiveness)
                task = await self.queue.dequeue(timeout=1.0)
                
                if task is None:
                    continue
                
                self.current_task = task
                await self._execute_task(task)
                self.current_task = None
                
            except asyncio.CancelledError:
                logger.info(f"Worker {self.worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}", exc_info=True)
                if self.current_task:
                    await self.queue.fail_task(
                        self.current_task.task_id,
                        f"Worker error: {e}"
                    )
        
        logger.info(f"Worker {self.worker_id} stopped")
    
    async def _execute_task(self, task: SearchTask):
        """
        Execute a single search task.
        
        Args:
            task: Task to execute
        """
        logger.info(
            f"Worker {self.worker_id} executing task {task.task_id[:8]}: "
            f"{task.source} query='{task.query[:50]}...'"
        )
        
        try:
            # Check cache first
            if task.resume_from_cache and task.cache_query_id:
                progress = self.cache.get_query_progress(task.cache_query_id)
                if progress and progress["completed"]:
                    logger.info(
                        f"Task {task.task_id[:8]} satisfied from cache "
                        f"({progress['total_papers']} papers)"
                    )
                    papers = self.cache.get_cached_papers(task.cache_query_id)
                    await self.queue.complete_task(
                        task.task_id,
                        papers,
                        from_cache=True
                    )
                    return
            
            # Execute search
            papers = await self.orchestrator.search_source(
                source=task.source,
                query=task.query,
                start_date=task.start_date,
                end_date=task.end_date,
                limit=task.limit,
                config=task.config,
                resume=task.resume_from_cache,
            )
            
            # Update progress
            task.papers_fetched = len(papers)
            
            # Complete task
            await self.queue.complete_task(task.task_id, papers)
            
        except Exception as e:
            logger.error(
                f"Task {task.task_id[:8]} failed: {e}",
                exc_info=True
            )
            await self.queue.fail_task(task.task_id, str(e))
    
    def stop(self):
        """Signal worker to stop."""
        self._stop_event.set()


class WorkerPool:
    """
    Pool of workers that process tasks concurrently.
    
    The worker pool manages multiple Worker instances, allowing parallel
    execution of search tasks. It handles worker lifecycle, graceful
    shutdown, and ensures all workers complete cleanly.
    
    Features:
    - Configurable concurrency
    - Graceful shutdown with timeout
    - Worker health monitoring
    - Automatic cleanup
    
    Example:
        >>> pool = WorkerPool(queue, orchestrator, cache, num_workers=3)
        >>> await pool.start()
        >>> await pool.wait_until_complete()
        >>> await pool.stop()
    """
    
    def __init__(
        self,
        queue: TaskQueue,
        orchestrator: SearchOrchestrator,
        cache: SearchCache,
        num_workers: int = 3,
    ):
        """
        Initialize worker pool.
        
        Args:
            queue: TaskQueue to pull tasks from
            orchestrator: SearchOrchestrator for executing searches
            cache: SearchCache for result persistence
            num_workers: Number of concurrent workers (default: 3)
        """
        self.queue = queue
        self.orchestrator = orchestrator
        self.cache = cache
        self.num_workers = num_workers
        
        self.workers: list[Worker] = []
        self.worker_tasks: list[asyncio.Task] = []
        self._running = False
    
    async def start(self):
        """Start all workers."""
        if self._running:
            logger.warning("Worker pool already running")
            return
        
        logger.info(f"Starting worker pool with {self.num_workers} workers")
        
        for i in range(self.num_workers):
            worker = Worker(
                worker_id=i,
                queue=self.queue,
                orchestrator=self.orchestrator,
                cache=self.cache,
            )
            self.workers.append(worker)
            
            task = asyncio.create_task(worker.run())
            self.worker_tasks.append(task)
        
        self._running = True
        logger.info("Worker pool started")
    
    async def stop(self, timeout: float = 30.0):
        """
        Stop all workers gracefully.
        
        Args:
            timeout: Max seconds to wait for workers to finish (default: 30)
        """
        if not self._running:
            return
        
        logger.info("Stopping worker pool...")
        
        # Signal all workers to stop
        for worker in self.workers:
            worker.stop()
        
        # Wait for workers to finish (with timeout)
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.worker_tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Worker pool stop timed out, cancelling tasks")
            for task in self.worker_tasks:
                task.cancel()
        
        self._running = False
        logger.info("Worker pool stopped")
    
    def is_running(self) -> bool:
        """
        Check if pool is running.
        
        Returns:
            True if workers are running
        """
        return self._running
    
    async def wait_until_complete(self, check_interval: float = 1.0):
        """
        Wait until all tasks are completed.
        
        Polls queue until both pending and running tasks are empty.
        
        Args:
            check_interval: Seconds between queue checks (default: 1.0)
        """
        while True:
            size = await self.queue.size()
            running = len(self.queue.running_tasks)
            
            if size == 0 and running == 0:
                logger.info("All tasks completed")
                break
            
            await asyncio.sleep(check_interval)
