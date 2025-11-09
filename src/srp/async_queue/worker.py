"""Worker pool for executing search tasks concurrently."""

import asyncio
from typing import Optional
from pathlib import Path

from .task_queue import TaskQueue, SearchTask, TaskStatus
from .error_handler import ErrorHandler, ErrorType
from ..search.orchestrator import SearchOrchestrator
from ..io.cache import SearchCache
from ..utils.logging import get_logger

logger = get_logger(__name__)


class Worker:
    """
    Single worker that processes tasks from queue.
    
    Workers run in an async loop, continuously fetching and executing
    tasks until stopped. Each worker operates independently and handles
    its own error recovery with intelligent retry strategies.
    
    Features:
    - Intelligent error classification and retry
    - Circuit breaker protection per source
    - Adaptive backoff strategies
    - Cache integration
    
    Attributes:
        worker_id: Unique worker identifier
        queue: Task queue to pull from
        orchestrator: Search orchestrator for executing searches
        cache: Cache for result persistence
        error_handler: Error handler with circuit breakers
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
        self.error_handler = ErrorHandler()
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
        Execute a single search task with intelligent error handling.
        
        Implements:
        - Cache checking
        - Retry loop with error classification
        - Circuit breaker protection
        - Adaptive backoff
        
        Args:
            task: Task to execute
        """
        logger.info(
            f"Worker {self.worker_id} executing task {task.task_id[:8]}: "
            f"{task.source} query='{task.query[:50]}...'"
        )
        
        # Check cache first
        if task.resume_from_cache and task.cache_query_id:
            try:
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
            except Exception as e:
                logger.warning(f"Cache check failed: {e}, proceeding with search")
        
        # Retry loop with intelligent error handling
        max_attempts = 5
        attempt = 0
        
        while attempt < max_attempts:
            attempt += 1
            
            try:
                # Get circuit breaker for this source
                circuit = await self.error_handler.get_circuit_breaker(task.source)
                
                # Execute search with circuit breaker protection
                papers = await circuit.call(
                    self.orchestrator.search_source,
                    source=task.source,
                    query=task.query,
                    start_date=task.start_date,
                    end_date=task.end_date,
                    limit=task.limit,
                    config=task.config,
                    resume=task.resume_from_cache,
                )
                
                # Success - update and complete
                task.papers_fetched = len(papers)
                await self.queue.complete_task(task.task_id, papers)
                
                logger.info(
                    f"Task {task.task_id[:8]} completed: {len(papers)} papers "
                    f"(attempt {attempt}/{max_attempts})"
                )
                return
                
            except Exception as e:
                # Classify error
                error_type = self.error_handler.classify_error(e)
                
                logger.warning(
                    f"Task {task.task_id[:8]} attempt {attempt}/{max_attempts} failed: "
                    f"{error_type.value} - {str(e)[:100]}"
                )
                
                # Check if should retry
                if not self.error_handler.should_retry(error_type, attempt, max_attempts):
                    logger.error(
                        f"Task {task.task_id[:8]} failed permanently after {attempt} attempts: "
                        f"{error_type.value}"
                    )
                    await self.queue.fail_task(
                        task.task_id, 
                        f"{error_type.value}: {str(e)}"
                    )
                    return
                
                # Calculate and apply backoff
                backoff = await self.error_handler.calculate_backoff(
                    error_type, 
                    attempt
                )
                logger.info(
                    f"Task {task.task_id[:8]} retrying in {backoff:.1f}s "
                    f"(attempt {attempt + 1}/{max_attempts})"
                )
                await asyncio.sleep(backoff)
        
        # Max attempts reached
        logger.error(f"Task {task.task_id[:8]} failed: max attempts reached")
        await self.queue.fail_task(
            task.task_id,
            f"Max retry attempts ({max_attempts}) exceeded"
        )
    
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
