"""Real-time progress tracking for search tasks."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.live import Live

from .task_queue import TaskQueue, TaskStatus
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueueStats:
    """Statistics about queue state."""
    total_tasks: int = 0
    pending: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cached: int = 0
    cancelled: int = 0
    total_papers: int = 0
    total_pages: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def elapsed_time(self) -> timedelta:
        if not self.started_at:
            return timedelta(0)
        end = self.completed_at or datetime.now()
        return end - self.started_at
    
    def papers_per_minute(self) -> float:
        elapsed = self.elapsed_time().total_seconds() / 60
        return self.total_papers / elapsed if elapsed > 0 else 0.0
    
    def completion_percentage(self) -> float:
        if self.total_tasks == 0:
            return 0.0
        done = self.completed + self.failed + self.cached + self.cancelled
        return (done / self.total_tasks) * 100


class ProgressTracker:
    """Track and display progress of search queue."""
    
    def __init__(self, queue: TaskQueue):
        self.queue = queue
        self.console = Console()
        self.started_at: Optional[datetime] = None
    
    def compute_stats(self) -> QueueStats:
        """Compute current queue statistics."""
        tasks = self.queue.get_all_tasks()
        
        stats = QueueStats(
            total_tasks=len(tasks),
            pending=len([t for t in tasks if t.status == TaskStatus.PENDING]),
            running=len([t for t in tasks if t.status == TaskStatus.RUNNING]),
            completed=len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            failed=len([t for t in tasks if t.status == TaskStatus.FAILED]),
            cached=len([t for t in tasks if t.status == TaskStatus.CACHED]),
            cancelled=len([t for t in tasks if t.status == TaskStatus.CANCELLED]),
            total_papers=sum(t.papers_fetched for t in tasks),
            total_pages=sum(t.pages_fetched for t in tasks),
            started_at=self.started_at or datetime.now(),
        )
        
        if stats.pending == 0 and stats.running == 0:
            stats.completed_at = datetime.now()
        
        return stats
    
    def print_summary(self):
        """Print summary table."""
        stats = self.compute_stats()
        
        table = Table(title="Search Queue Summary", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Total Tasks", str(stats.total_tasks))
        table.add_row("Pending", str(stats.pending))
        table.add_row("Running", str(stats.running))
        table.add_row("Completed", str(stats.completed))
        table.add_row("From Cache", str(stats.cached))
        table.add_row("Failed", str(stats.failed))
        table.add_row("Cancelled", str(stats.cancelled))
        table.add_row("", "")
        table.add_row("Papers Fetched", str(stats.total_papers))
        table.add_row("Pages Fetched", str(stats.total_pages))
        table.add_row("", "")
        table.add_row("Elapsed Time", str(stats.elapsed_time()).split('.')[0])
        table.add_row("Papers/min", f"{stats.papers_per_minute():.1f}")
        table.add_row("Progress", f"{stats.completion_percentage():.1f}%")
        
        self.console.print(table)
    
    async def watch(self, interval: float = 2.0):
        """Watch queue progress in real-time."""
        if not self.started_at:
            self.started_at = datetime.now()
        
        with Live(console=self.console, refresh_per_second=1) as live:
            while True:
                stats = self.compute_stats()
                
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Status", style="cyan")
                table.add_column("Count", justify="right")
                table.add_column("Papers", justify="right")
                
                table.add_row("Pending", str(stats.pending), "-")
                table.add_row("Running", str(stats.running), "-")
                table.add_row("Completed", str(stats.completed), str(stats.total_papers))
                table.add_row("Cached", str(stats.cached), "-")
                table.add_row("Failed", str(stats.failed), "-")
                table.add_row("", "", "")
                table.add_row(
                    "Progress",
                    f"{stats.completion_percentage():.1f}%",
                    f"{stats.papers_per_minute():.1f}/min"
                )
                table.add_row(
                    "Elapsed",
                    str(stats.elapsed_time()).split('.')[0],
                    ""
                )
                
                live.update(table)
                
                if stats.pending == 0 and stats.running == 0:
                    break
                
                await asyncio.sleep(interval)
