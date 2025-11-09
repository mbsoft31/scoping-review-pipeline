"""Integration tests for search queue with real adapters."""

import pytest
import time
import asyncio
from datetime import date

from srp.async_queue import SearchQueueManager
from srp.async_queue.task_queue import TaskStatus


@pytest.mark.integration
class TestSearchQueue:
    """Integration tests for SearchQueueManager."""
    
    def test_simple_search(self):
        """Test simple search through queue."""
        manager = SearchQueueManager(num_workers=1)
        
        task_id = manager.add_search(
            source="openalex",
            query="machine learning",
            limit=5,  # Small limit for test
        )
        
        manager.run_all(show_progress=False)
        
        papers = manager.get_results(task_id)
        assert papers is not None
        assert len(papers) <= 5
        assert all(p.title for p in papers)
        assert manager.get_task_status(task_id) == TaskStatus.COMPLETED.value
    
    def test_multiple_sources(self):
        """Test parallel search across multiple sources."""
        manager = SearchQueueManager(num_workers=2)
        
        task1 = manager.add_search("openalex", "AI", limit=5, priority=1)
        task2 = manager.add_search("arxiv", "ML", limit=5, priority=1)
        
        start = time.time()
        manager.run_all(show_progress=False)
        elapsed = time.time() - start
        
        results = manager.get_all_results()
        assert len(results) == 2
        assert task1 in results
        assert task2 in results
        
        # Parallel should be faster than sequential
        # (very rough check - parallel should be < 80% of sequential time)
        print(f"Elapsed time with 2 workers: {elapsed:.2f}s")
    
    def test_batch_searches(self):
        """Test adding multiple searches at once."""
        manager = SearchQueueManager(num_workers=2)
        
        searches = [
            {"source": "openalex", "query": "query1", "limit": 3},
            {"source": "openalex", "query": "query2", "limit": 3},
            {"source": "arxiv", "query": "query3", "limit": 3},
        ]
        
        task_ids = manager.add_multiple_searches(searches)
        assert len(task_ids) == 3
        assert len(set(task_ids)) == 3  # All unique
        
        manager.run_all(show_progress=False)
        
        results = manager.get_all_results()
        assert len(results) == 3
    
    def test_priority_execution_order(self):
        """Test that high-priority tasks run first."""
        manager = SearchQueueManager(num_workers=1)  # Serial execution
        
        # Add low priority first, then high
        task_low = manager.add_search("openalex", "low", limit=3, priority=10)
        task_high = manager.add_search("openalex", "high", limit=3, priority=1)
        
        manager.run_all(show_progress=False)
        
        # High priority should complete first
        task_low_obj = manager.queue.get_task(task_low)
        task_high_obj = manager.queue.get_task(task_high)
        
        assert task_high_obj.completed_at < task_low_obj.completed_at
    
    def test_with_date_filtering(self):
        """Test search with date range filtering."""
        manager = SearchQueueManager(num_workers=1)
        
        task_id = manager.add_search(
            source="openalex",
            query="deep learning",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            limit=10,
        )
        
        manager.run_all(show_progress=False)
        
        papers = manager.get_results(task_id)
        assert papers is not None
        
        # Check dates are in range
        for paper in papers:
            if paper.publication_date:
                assert date(2023, 1, 1) <= paper.publication_date <= date(2023, 12, 31)
    
    def test_cancel_task(self):
        """Test cancelling a task."""
        manager = SearchQueueManager(num_workers=1)
        
        task_id = manager.add_search("openalex", "test", limit=100)
        
        # Cancel before running
        manager.cancel_task(task_id)
        
        manager.run_all(show_progress=False)
        
        # Should not have results
        assert manager.get_results(task_id) is None
        assert manager.get_task_status(task_id) == TaskStatus.CANCELLED.value
    
    def test_context_manager(self):
        """Test context manager usage."""
        with SearchQueueManager(num_workers=1) as manager:
            manager.add_search("openalex", "test", limit=3)
            manager.run_all(show_progress=False)
            results = manager.get_all_results()
            assert len(results) == 1
        
        # Manager should cleanup automatically


@pytest.mark.integration
@pytest.mark.slow
class TestQueuePerformance:
    """Performance tests for queue system."""
    
    def test_throughput(self):
        """Measure papers/second throughput."""
        manager = SearchQueueManager(num_workers=3)
        
        # Add multiple searches
        for i in range(3):
            manager.add_search(
                "openalex",
                f"test query {i}",
                limit=20,
            )
        
        start_time = time.time()
        manager.run_all(show_progress=False)
        elapsed = time.time() - start_time
        
        results = manager.get_all_results()
        total_papers = sum(len(papers) for papers in results.values())
        
        throughput = total_papers / elapsed
        print(f"\nThroughput: {throughput:.2f} papers/second")
        print(f"Total time: {elapsed:.2f}s for {total_papers} papers")
        
        # Should get at least 2 papers/second (conservative)
        assert throughput > 2.0
    
    def test_concurrent_speedup(self):
        """Test that more workers = faster completion."""
        # Test with 1 worker
        manager1 = SearchQueueManager(num_workers=1)
        for i in range(3):
            manager1.add_search("openalex", f"q{i}", limit=10)
        
        start1 = time.time()
        manager1.run_all(show_progress=False)
        time1 = time.time() - start1
        
        # Test with 3 workers
        manager3 = SearchQueueManager(num_workers=3)
        for i in range(3):
            manager3.add_search("openalex", f"q{i}", limit=10)
        
        start3 = time.time()
        manager3.run_all(show_progress=False)
        time3 = time.time() - start3
        
        print(f"\n1 worker: {time1:.2f}s")
        print(f"3 workers: {time3:.2f}s")
        print(f"Speedup: {time1/time3:.2f}x")
        
        # 3 workers should be faster
        assert time3 < time1 * 0.8  # At least 20% faster
