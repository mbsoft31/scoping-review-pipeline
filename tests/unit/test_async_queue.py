"""Unit tests for async queue system."""

import pytest
import asyncio
import tempfile
from pathlib import Path
from datetime import date

from srp.async_queue.task_queue import TaskQueue, SearchTask, TaskStatus
from srp.core.models import Paper, Author


class TestSearchTask:
    """Test SearchTask model."""
    
    def test_create_task(self):
        """Test creating a search task."""
        task = SearchTask(
            source="openalex",
            query="test query",
            priority=1,
            limit=100,
        )
        
        assert task.source == "openalex"
        assert task.query == "test query"
        assert task.priority == 1
        assert task.limit == 100
        assert task.status == TaskStatus.PENDING
        assert task.task_id is not None
    
    def test_task_serialization(self):
        """Test task to_dict and from_dict."""
        task = SearchTask(
            source="arxiv",
            query="machine learning",
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
            limit=50,
        )
        
        # Serialize
        data = task.to_dict()
        assert data["source"] == "arxiv"
        assert data["query"] == "machine learning"
        assert data["start_date"] == "2023-01-01"
        
        # Deserialize
        restored = SearchTask.from_dict(data)
        assert restored.source == task.source
        assert restored.query == task.query
        assert restored.start_date == task.start_date
        assert restored.task_id == task.task_id


class TestTaskQueue:
    """Test TaskQueue operations."""
    
    @pytest.mark.asyncio
    async def test_enqueue_dequeue(self):
        """Test basic enqueue/dequeue."""
        queue = TaskQueue()
        
        task = SearchTask(
            source="openalex",
            query="test query",
            priority=1
        )
        
        task_id = await queue.enqueue(task)
        assert task_id == task.task_id
        assert await queue.size() == 1
        
        dequeued = await queue.dequeue(timeout=1.0)
        assert dequeued is not None
        assert dequeued.task_id == task_id
        assert dequeued.status == TaskStatus.RUNNING
        assert await queue.size() == 0
    
    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        """Test that tasks are dequeued by priority."""
        queue = TaskQueue()
        
        # Add tasks with different priorities
        task_low = SearchTask(source="openalex", query="low", priority=10)
        task_high = SearchTask(source="openalex", query="high", priority=1)
        task_med = SearchTask(source="openalex", query="med", priority=5)
        
        await queue.enqueue(task_low)
        await queue.enqueue(task_high)
        await queue.enqueue(task_med)
        
        # Should dequeue in priority order
        first = await queue.dequeue(timeout=1.0)
        assert first.query == "high"
        
        second = await queue.dequeue(timeout=1.0)
        assert second.query == "med"
        
        third = await queue.dequeue(timeout=1.0)
        assert third.query == "low"
    
    @pytest.mark.asyncio
    async def test_task_retry(self):
        """Test that failed tasks are retried."""
        queue = TaskQueue(max_retries=3)
        
        task = SearchTask(
            source="openalex",
            query="test",
            max_retries=3
        )
        task_id = await queue.enqueue(task)
        
        # Dequeue and fail
        dequeued = await queue.dequeue()
        assert dequeued is not None
        
        await queue.fail_task(task_id, "Test error")
        
        # Should be re-queued
        assert await queue.size() == 1
        assert queue.tasks[task_id].retry_count == 1
        assert queue.tasks[task_id].status == TaskStatus.PENDING
        assert queue.tasks[task_id].error == "Test error"
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that task fails permanently after max retries."""
        queue = TaskQueue(max_retries=2)
        
        task = SearchTask(source="openalex", query="test", max_retries=2)
        task_id = await queue.enqueue(task)
        
        # Fail twice (reach max)
        await queue.dequeue()
        await queue.fail_task(task_id, "Error 1")
        
        await queue.dequeue()
        await queue.fail_task(task_id, "Error 2")
        
        # Should be permanently failed
        assert queue.tasks[task_id].status == TaskStatus.FAILED
        assert queue.tasks[task_id].retry_count == 2
        assert await queue.size() == 0  # Not re-queued
    
    @pytest.mark.asyncio
    async def test_complete_task(self):
        """Test task completion."""
        queue = TaskQueue()
        
        task = SearchTask(source="openalex", query="test")
        task_id = await queue.enqueue(task)
        
        await queue.dequeue()
        
        papers = [
            Paper(
                paper_id="test1",
                title="Test Paper",
                authors=[Author(name="Test Author")],
            )
        ]
        
        await queue.complete_task(task_id, papers)
        
        assert queue.tasks[task_id].status == TaskStatus.COMPLETED
        assert len(queue.tasks[task_id].papers) == 1
        assert queue.tasks[task_id].papers_fetched == 1
    
    @pytest.mark.asyncio
    async def test_complete_from_cache(self):
        """Test task completion from cache."""
        queue = TaskQueue()
        
        task = SearchTask(source="openalex", query="test")
        task_id = await queue.enqueue(task)
        await queue.dequeue()
        
        papers = [Paper(paper_id="test1", title="Test", authors=[])]
        await queue.complete_task(task_id, papers, from_cache=True)
        
        assert queue.tasks[task_id].status == TaskStatus.CACHED
    
    @pytest.mark.asyncio
    async def test_cancel_task(self):
        """Test task cancellation."""
        queue = TaskQueue()
        
        task = SearchTask(source="openalex", query="test")
        task_id = await queue.enqueue(task)
        
        await queue.cancel_task(task_id)
        
        assert queue.tasks[task_id].status == TaskStatus.CANCELLED
        assert await queue.size() == 0
    
    @pytest.mark.asyncio
    async def test_persistence(self):
        """Test that queue state is persisted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            
            # Create queue and add task
            queue1 = TaskQueue(state_file=state_file)
            task = SearchTask(source="openalex", query="persist test")
            task_id = await queue1.enqueue(task)
            
            # Create new queue (should load state)
            queue2 = TaskQueue(state_file=state_file)
            assert task_id in queue2.tasks
            assert queue2.tasks[task_id].query == "persist test"
            assert queue2.tasks[task_id].status == TaskStatus.PENDING
    
    @pytest.mark.asyncio
    async def test_get_tasks_by_status(self):
        """Test filtering tasks by status."""
        queue = TaskQueue()
        
        # Add multiple tasks
        task1 = SearchTask(source="openalex", query="q1")
        task2 = SearchTask(source="openalex", query="q2")
        task3 = SearchTask(source="openalex", query="q3")
        
        id1 = await queue.enqueue(task1)
        id2 = await queue.enqueue(task2)
        id3 = await queue.enqueue(task3)
        
        # Change statuses
        await queue.dequeue()  # task1 -> RUNNING
        await queue.complete_task(id1, [])
        await queue.cancel_task(id3)
        
        # Test filtering
        pending = queue.get_tasks_by_status(TaskStatus.PENDING)
        completed = queue.get_tasks_by_status(TaskStatus.COMPLETED)
        cancelled = queue.get_tasks_by_status(TaskStatus.CANCELLED)
        
        assert len(pending) == 1
        assert len(completed) == 1
        assert len(cancelled) == 1
        assert pending[0].task_id == id2
    
    @pytest.mark.asyncio
    async def test_dequeue_timeout(self):
        """Test dequeue timeout on empty queue."""
        queue = TaskQueue()
        
        # Try to dequeue from empty queue with timeout
        task = await queue.dequeue(timeout=0.5)
        assert task is None
    
    @pytest.mark.asyncio
    async def test_max_queue_size(self):
        """Test queue size limit."""
        queue = TaskQueue(max_size=5)
        
        # Add up to limit
        for i in range(5):
            task = SearchTask(source="openalex", query=f"q{i}")
            await queue.enqueue(task)
        
        # Try to add one more (should fail)
        with pytest.raises(ValueError, match="Queue full"):
            task = SearchTask(source="openalex", query="overflow")
            await queue.enqueue(task)


class TestConcurrency:
    """Test concurrent queue operations."""
    
    @pytest.mark.asyncio
    async def test_concurrent_enqueue(self):
        """Test multiple concurrent enqueue operations."""
        queue = TaskQueue()
        
        async def enqueue_task(i):
            task = SearchTask(source="openalex", query=f"query {i}")
            return await queue.enqueue(task)
        
        # Enqueue 10 tasks concurrently
        task_ids = await asyncio.gather(*[enqueue_task(i) for i in range(10)])
        
        assert len(task_ids) == 10
        assert len(set(task_ids)) == 10  # All unique
        assert await queue.size() == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_dequeue(self):
        """Test multiple workers dequeuing concurrently."""
        queue = TaskQueue()
        
        # Add 10 tasks
        for i in range(10):
            task = SearchTask(source="openalex", query=f"q{i}")
            await queue.enqueue(task)
        
        # Dequeue with 3 workers
        async def worker_dequeue():
            tasks = []
            for _ in range(4):
                task = await queue.dequeue(timeout=1.0)
                if task:
                    tasks.append(task)
            return tasks
        
        results = await asyncio.gather(*[worker_dequeue() for _ in range(3)])
        
        # All tasks should be dequeued
        all_dequeued = [task for worker_tasks in results for task in worker_tasks]
        assert len(all_dequeued) == 10
        
        # All should be unique
        task_ids = [t.task_id for t in all_dequeued]
        assert len(set(task_ids)) == 10
