"""Real-time progress tracking for search tasks."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .task_queue import TaskQueue, TaskStatus
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class QueueStats:
    """
    Statistics about queue state.
    
    Attributes:
        total_tasks: Total number of tasks
        pending: Tasks waiting to execute
        running: Tasks currently executing
        completed: Successfully completed tasks
        failed: Failed tasks (after max retries)
        cached: Tasks satisfied from cache
        cancelled: Manually cancelled tasks
        total_papers: Total papers collected
        total_pages: Total API pages fetched
        started_at: When execution started
        completed_at: When all tasks completed
    """
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
        """Time elapsed since start."""
        if not self.started_at:
            return timedelta(0)
        end = self.completed_at or datetime.now()
        return end - self.started_at
    
    def papers_per_minute(self) -> float:
        """Papers fetched per minute."""
        elapsed = self.elapsed_time().total_seconds() / 60
        return self.total_papers / elapsed if elapsed > 0 else 0.0
    
    def completion_percentage(self) -> float:
        """Percentage of tasks completed."""
        if self.total_tasks == 0:
            return 0.0
        done = self.completed + self.failed + self.cached + self.cancelled
        return (done / self.total_tasks) * 100


class ProgressTracker:
    """
    Track and display progress of search queue.
    
    Provides real-time monitoring of queue execution with:
    - Task status breakdown
    - Paper collection statistics
    - Performance metrics
    - ETA calculation
    
    Can display progress using Rich library if available, falls back
    to simple logging otherwise.
    
    Example:
        >>> tracker = ProgressTracker(queue)
        >>> tracker.print_summary()  # One-time summary
        >>> await tracker.watch()    # Live updates (blocking)
    """
    
    def __init__(self, queue: TaskQueue, use_rich: bool = True):
        """
        Initialize progress tracker.
        
        Args:
            queue: TaskQueue to monitor
            use_rich: Use rich formatting if available (default: True)
        """
        self.queue = queue
        self.started_at: Optional[datetime] = None
        self.use_rich = use_rich and HAS_RICH
        
        if self.use_rich:
            self.console = Console()
        else:
            self.console = None
            if use_rich:
                logger.warning("Rich not installed, falling back to simple output")
    
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
        
        # Set completed_at if all done
        if stats.pending == 0 and stats.running == 0:
            stats.completed_at = datetime.now()
        
        return stats
    
    def print_summary(self):
        """Print summary table."""
        stats = self.compute_stats()
        
        if self.use_rich and self.console:
            self._print_rich_summary(stats)
        else:
            self._print_simple_summary(stats)
    
    def _print_rich_summary(self, stats: QueueStats):
        """Print Rich formatted summary."""
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
    
    def _print_simple_summary(self, stats: QueueStats):
        """Print simple text summary."""
        print("\n=== Search Queue Summary ===")
        print(f"Total Tasks: {stats.total_tasks}")
        print(f"  Pending: {stats.pending}")
        print(f"  Running: {stats.running}")
        print(f"  Completed: {stats.completed}")
        print(f"  From Cache: {stats.cached}")
        print(f"  Failed: {stats.failed}")
        print(f"  Cancelled: {stats.cancelled}")
        print(f"\nPapers Fetched: {stats.total_papers}")
        print(f"Pages Fetched: {stats.total_pages}")
        print(f"\nElapsed Time: {str(stats.elapsed_time()).split('.')[0]}")
        print(f"Papers/min: {stats.papers_per_minute():.1f}")
        print(f"Progress: {stats.completion_percentage():.1f}%")
        print("===========================\n")
    
    async def watch(self, interval: float = 2.0):
        """
        Watch queue progress in real-time (blocking).
        
        Args:
            interval: Update interval in seconds (default: 2.0)
        """
        if not self.started_at:
            self.started_at = datetime.now()
        
        if self.use_rich and self.console:
            await self._watch_rich(interval)
        else:
            await self._watch_simple(interval)
    
    async def _watch_rich(self, interval: float):
        """Watch with Rich live display."""
        with Live(console=self.console, refresh_per_second=1) as live:
            while True:
                stats = self.compute_stats()
                
                # Build display table
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
                
                # Stop if all done
                if stats.pending == 0 and stats.running == 0:
                    break
                
                await asyncio.sleep(interval)
    
    async def _watch_simple(self, interval: float):
        """Watch with simple periodic updates."""
        while True:
            stats = self.compute_stats()
            
            print(f"\rProgress: {stats.completion_percentage():.1f}% | "
                  f"Pending: {stats.pending} | Running: {stats.running} | "
                  f"Completed: {stats.completed} | Papers: {stats.total_papers}",
                  end="", flush=True)
            
            if stats.pending == 0 and stats.running == 0:
                print()  # New line
                break
            
            await asyncio.sleep(interval)
