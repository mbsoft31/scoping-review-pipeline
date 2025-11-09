#!/usr/bin/env python3
"""
Comprehensive examples for using the async task queue system.

These examples show common usage patterns without requiring
any async/await knowledge.
"""

from datetime import date
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from srp.async_queue import SearchQueueManager
from srp.search.strategy import SearchStrategy


def example_1_basic():
    """
    Example 1: Basic usage - the simplest way to use the queue.
    
    No async knowledge required!
    """
    print("\n" + "="*60)
    print("Example 1: Basic Usage")
    print("="*60)
    
    # Create manager (default 3 workers)
    manager = SearchQueueManager(num_workers=3)
    
    # Add searches
    print("\nAdding searches...")
    task1 = manager.add_search(
        source="openalex",
        query="machine learning fairness",
        limit=50,
        priority=1  # High priority
    )
    
    task2 = manager.add_search(
        source="arxiv",
        query="neural network interpretability",
        limit=30,
        priority=2  # Lower priority (runs after task1)
    )
    
    print(f"Task 1 ID: {task1[:8]}...")
    print(f"Task 2 ID: {task2[:8]}...")
    print(f"Queue size: {manager.get_queue_size()}")
    
    # Run all (blocks until done, shows progress)
    print("\nRunning searches...")
    manager.run_all()
    
    # Get results
    papers1 = manager.get_results(task1)
    papers2 = manager.get_results(task2)
    
    print(f"\nResults:")
    print(f"  Task 1: {len(papers1)} papers")
    print(f"  Task 2: {len(papers2)} papers")
    print(f"  Total: {len(papers1) + len(papers2)} papers")


def example_2_batch():
    """
    Example 2: Batch searches - add multiple searches at once.
    """
    print("\n" + "="*60)
    print("Example 2: Batch Searches")
    print("="*60)
    
    manager = SearchQueueManager(num_workers=5)
    
    # Define multiple searches
    searches = [
        {
            "source": "openalex",
            "query": "transfer learning",
            "limit": 100,
            "priority": 1,
        },
        {
            "source": "openalex",
            "query": "few-shot learning",
            "limit": 80,
            "priority": 1,
        },
        {
            "source": "arxiv",
            "query": "meta-learning",
            "limit": 60,
            "priority": 2,
        },
    ]
    
    # Add all at once
    print("\nAdding batch searches...")
    task_ids = manager.add_multiple_searches(searches)
    print(f"Added {len(task_ids)} searches")
    
    # Run
    print("\nRunning searches...")
    manager.run_all(show_progress=True)
    
    # Get all results
    all_results = manager.get_all_results()
    total_papers = sum(len(papers) for papers in all_results.values())
    
    print(f"\nResults:")
    for i, task_id in enumerate(task_ids, 1):
        papers = manager.get_results(task_id)
        query = searches[i-1]["query"]
        print(f"  {query}: {len(papers)} papers")
    print(f"  Total: {total_papers} papers")


def example_3_date_filtering():
    """
    Example 3: Date filtering and cache resume.
    """
    print("\n" + "="*60)
    print("Example 3: Date Filtering with Cache Resume")
    print("="*60)
    
    manager = SearchQueueManager(
        num_workers=4,
        cache_dir=Path(".cache/examples")
    )
    
    # Add search with date range
    print("\nAdding search with date filter...")
    task_id = manager.add_search(
        source="openalex",
        query="climate change adaptation",
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        limit=200,
        priority=0,
        resume_from_cache=True,  # Resume if interrupted
    )
    
    print(f"Task ID: {task_id[:8]}...")
    print(f"Date range: 2020-01-01 to 2024-12-31")
    
    # Run (if this crashes/stops, just run again and it resumes!)
    print("\nRunning search...")
    print("(If interrupted, run again to resume from cache)")
    manager.run_all()
    
    # Get results
    papers = manager.get_results(task_id)
    print(f"\nResults: {len(papers)} papers on climate adaptation (2020-2024)")
    
    # Show some paper years
    if papers:
        years = [p.year for p in papers[:10] if p.year]
        print(f"First 10 paper years: {years}")


def example_4_monitoring():
    """
    Example 4: Monitor progress and cancel tasks.
    """
    print("\n" + "="*60)
    print("Example 4: Monitoring and Cancellation")
    print("="*60)
    
    manager = SearchQueueManager(num_workers=3)
    
    # Add several searches
    print("\nAdding searches...")
    task1 = manager.add_search("openalex", "quantum computing", limit=100)
    task2 = manager.add_search("openalex", "blockchain", limit=100)
    task3 = manager.add_search("arxiv", "deep learning", limit=50)
    
    print(f"Queue size: {manager.get_queue_size()}")
    
    # Check status
    print(f"\nTask statuses:")
    print(f"  Task 1: {manager.get_task_status(task1)}")
    print(f"  Task 2: {manager.get_task_status(task2)}")
    print(f"  Task 3: {manager.get_task_status(task3)}")
    
    # Cancel one task
    print(f"\nCancelling task 3...")
    manager.cancel_task(task3)
    
    print(f"Queue size after cancel: {manager.get_queue_size()}")
    print(f"Task 3 status: {manager.get_task_status(task3)}")
    
    # Run remaining
    print("\nRunning remaining searches...")
    manager.run_all()
    
    # Check final statuses
    print(f"\nFinal statuses:")
    print(f"  Task 1: {manager.get_task_status(task1)}")
    print(f"  Task 2: {manager.get_task_status(task2)}")
    print(f"  Task 3: {manager.get_task_status(task3)}")


def example_5_context_manager():
    """
    Example 5: Context manager for automatic cleanup.
    """
    print("\n" + "="*60)
    print("Example 5: Context Manager")
    print("="*60)
    
    # Context manager auto-closes cache and event loop
    with SearchQueueManager(num_workers=3) as manager:
        # Add searches
        print("\nAdding searches...")
        manager.add_search("openalex", "artificial intelligence", limit=50)
        manager.add_search("arxiv", "machine learning", limit=30)
        
        # Run
        print("\nRunning searches...")
        manager.run_all()
        
        # Get results
        results = manager.get_all_results()
        total = sum(len(p) for p in results.values())
        print(f"\nTotal papers: {total}")
    
    # Cleanup happens automatically when exiting context
    print("\nCleanup complete (automatic)")


def example_6_priority_demonstration():
    """
    Example 6: Demonstrate priority execution order.
    """
    print("\n" + "="*60)
    print("Example 6: Priority Demonstration")
    print("="*60)
    
    manager = SearchQueueManager(num_workers=1)  # Single worker to see order
    
    # Add searches with different priorities
    print("\nAdding searches with priorities...")
    tasks = [
        manager.add_search("openalex", "low priority query", limit=20, priority=10),
        manager.add_search("openalex", "high priority query", limit=20, priority=0),
        manager.add_search("openalex", "medium priority query", limit=20, priority=5),
    ]
    
    print("\nExecution order (1 worker):")
    print("  1. High priority (priority=0)")
    print("  2. Medium priority (priority=5)")
    print("  3. Low priority (priority=10)")
    
    # Run - watch order in progress output
    print("\nRunning (watch the order in logs)...")
    manager.run_all(show_progress=False)  # Less output to see order clearly
    
    print("\nAll completed!")


def example_7_error_handling():
    """
    Example 7: Handling errors and retries.
    """
    print("\n" + "="*60)
    print("Example 7: Error Handling")
    print("="*60)
    
    manager = SearchQueueManager(num_workers=2)
    
    # Add some searches (some might fail due to API issues)
    print("\nAdding searches...")
    tasks = [
        manager.add_search("openalex", "valid query", limit=50),
        manager.add_search("openalex", "another query", limit=50),
    ]
    
    # Run with automatic retries
    print("\nRunning (automatic retry on failures)...")
    manager.run_all()
    
    # Check which succeeded and which failed
    print("\nResults:")
    for task_id in tasks:
        status = manager.get_task_status(task_id)
        print(f"  Task {task_id[:8]}: {status}")
        
        if status == "completed":
            papers = manager.get_results(task_id)
            print(f"    Papers: {len(papers)}")
        elif status == "failed":
            task = manager.queue.get_task(task_id)
            print(f"    Error: {task.error}")
            print(f"    Retries: {task.retry_count}/{task.max_retries}")


def run_all_examples():
    """
    Run all examples in sequence.
    """
    examples = [
        ("Basic Usage", example_1_basic),
        ("Batch Searches", example_2_batch),
        ("Date Filtering", example_3_date_filtering),
        ("Monitoring", example_4_monitoring),
        ("Context Manager", example_5_context_manager),
        ("Priority", example_6_priority_demonstration),
        ("Error Handling", example_7_error_handling),
    ]
    
    print("\n" + "#"*60)
    print("# Async Queue Usage Examples")
    print("#"*60)
    
    for name, func in examples:
        try:
            func()
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"\n\nExample '{name}' failed: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print("\n" + "#"*60)
    print("# All examples completed!")
    print("#"*60)


if __name__ == "__main__":
    # Run all examples
    run_all_examples()
    
    # Or run individual examples:
    # example_1_basic()
    # example_2_batch()
    # example_3_date_filtering()
    # example_4_monitoring()
    # example_5_context_manager()
    # example_6_priority_demonstration()
    # example_7_error_handling()
