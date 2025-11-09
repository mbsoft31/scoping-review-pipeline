"""Core task queue with state management and persistence."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from collections import deque
import json

from ..utils.logging import get_logger
from ..core.models import Paper

logger = get_logger(__name__)


class TaskStatus(Enum):
    """Task execution states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CACHED = "cached"


@dataclass
class SearchTask:
    """A single search task with all necessary metadata."""
    
    # Identity
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Search parameters
    source: str = ""
    query: str = ""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: Optional[int] = None
    
    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    
    # State
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    papers: List[Paper] = field(default_factory=list)
    error: Optional[str] = None
    
    # Progress tracking
    pages_fetched: int = 0
    papers_fetched: int = 0
    retry_count: int = 0
    max_retries: int = 3
    
    # Cache
    cache_query_id: Optional[str] = None
    resume_from_cache: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for persistence."""
        return {
            "task_id": self.task_id,
            "source": self.source,
            "query": self.query,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "limit": self.limit,
            "config": self.config,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "pages_fetched": self.pages_fetched,
            "papers_fetched": self.papers_fetched,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "cache_query_id": self.cache_query_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchTask":
        """Deserialize from dict."""
        task = cls(
            task_id=data["task_id"],
            source=data["source"],
            query=data["query"],
            start_date=date.fromisoformat(data["start_date"]) if data.get("start_date") else None,
            end_date=date.fromisoformat(data["end_date"]) if data.get("end_date") else None,
            limit=data.get("limit"),
            config=data.get("config", {}),
            priority=data.get("priority", 0),
            status=TaskStatus(data["status"]),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            cache_query_id=data.get("cache_query_id"),
        )
        task.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("started_at"):
            task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            task.completed_at = datetime.fromisoformat(data["completed_at"])
        task.error = data.get("error")
        task.pages_fetched = data.get("pages_fetched", 0)
        task.papers_fetched = data.get("papers_fetched", 0)
        return task


class TaskQueue:
    """Priority queue for search tasks with persistence."""
    
    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or Path(".cache/task_queue_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.tasks: Dict[str, SearchTask] = {}
        self.pending_queue: deque[str] = deque()
        self.running_tasks: Dict[str, SearchTask] = {}
        
        self._load_state()
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
    
    async def enqueue(self, task: SearchTask) -> str:
        """Add task to queue."""
        async with self._lock:
            self.tasks[task.task_id] = task
            self.pending_queue.append(task.task_id)
            
            # Sort by priority
            self.pending_queue = deque(
                sorted(self.pending_queue, key=lambda tid: self.tasks[tid].priority)
            )
            
            logger.info(
                f"Enqueued task {task.task_id[:8]}: {task.source} query='{task.query[:50]}...' priority={task.priority}"
            )
            
            self._save_state()
            self._not_empty.notify()
            return task.task_id
    
    async def dequeue(self, timeout: Optional[float] = None) -> Optional[SearchTask]:
        """Get next task from queue."""
        async with self._not_empty:
            while not self.pending_queue:
                try:
                    await asyncio.wait_for(self._not_empty.wait(), timeout=timeout)
                except asyncio.TimeoutError:
                    return None
            
            task_id = self.pending_queue.popleft()
            task = self.tasks[task_id]
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()
            self.running_tasks[task_id] = task
            
            self._save_state()
            return task
    
    async def complete_task(self, task_id: str, papers: List[Paper], from_cache: bool = False):
        """Mark task as completed."""
        async with self._lock:
            if task_id not in self.tasks:
                return
            
            task = self.tasks[task_id]
            task.status = TaskStatus.CACHED if from_cache else TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.papers = papers
            task.papers_fetched = len(papers)
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            logger.info(f"Task {task_id[:8]} completed: {len(papers)} papers ({task.status.value})")
            self._save_state()
    
    async def fail_task(self, task_id: str, error: str):
        """Mark task as failed."""
        async with self._lock:
            if task_id not in self.tasks:
                return
            
            task = self.tasks[task_id]
            task.retry_count += 1
            
            if task.retry_count < task.max_retries:
                logger.warning(
                    f"Task {task_id[:8]} failed (retry {task.retry_count}/{task.max_retries}): {error}"
                )
                task.status = TaskStatus.PENDING
                task.error = error
                self.pending_queue.append(task_id)
                task.priority += 10
            else:
                logger.error(
                    f"Task {task_id[:8]} failed permanently after {task.retry_count} retries: {error}"
                )
                task.status = TaskStatus.FAILED
                task.error = error
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self._save_state()
    
    async def cancel_task(self, task_id: str):
        """Cancel a task."""
        async with self._lock:
            if task_id not in self.tasks:
                return
            
            task = self.tasks[task_id]
            task.status = TaskStatus.CANCELLED
            
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.pending_queue:
                self.pending_queue.remove(task_id)
            
            logger.info(f"Task {task_id[:8]} cancelled")
            self._save_state()
    
    def get_task(self, task_id: str) -> Optional[SearchTask]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[SearchTask]:
        """Get all tasks."""
        return list(self.tasks.values())
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[SearchTask]:
        """Get tasks with specific status."""
        return [t for t in self.tasks.values() if t.status == status]
    
    async def size(self) -> int:
        """Number of pending tasks."""
        async with self._lock:
            return len(self.pending_queue)
    
    def _save_state(self):
        """Persist queue state."""
        state = {
            "tasks": {tid: task.to_dict() for tid, task in self.tasks.items()},
            "pending_queue": list(self.pending_queue),
            "saved_at": datetime.now().isoformat(),
        }
        self.state_file.write_text(json.dumps(state, indent=2))
    
    def _load_state(self):
        """Load queue state."""
        if not self.state_file.exists():
            return
        
        try:
            state = json.loads(self.state_file.read_text())
            for task_id, task_data in state["tasks"].items():
                task = SearchTask.from_dict(task_data)
                self.tasks[task_id] = task
                if task.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    task.status = TaskStatus.PENDING
                    self.pending_queue.append(task_id)
            
            logger.info(
                f"Restored {len(self.tasks)} tasks from state ({len(self.pending_queue)} pending)"
            )
        except Exception as e:
            logger.error(f"Failed to load queue state: {e}")
