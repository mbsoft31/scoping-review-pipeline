"""Simple examples showing how to use SearchQueueManager.

No async knowledge required!
"""

from datetime import date
from pathlib import Path
import sys

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from srp.async_queue import SearchQueueManager


def example_1_basic():
    """Most simple usage - just add searches and run."""
    print("\n=== Example 1: Basic Usage ===")
    
    # Create manager (default 3 workers)
    manager = SearchQueueManager(num_workers=3)
    
    # Add searches
    task1 = manager.add_search(
        source="openalex",
        query="machine learning fairness",
        limit=10,  # Small limit for demo
        priority=1  # High priority
    )
    
    task2 = manager.add_search(
        source="arxiv",
        query="neural network interpretability",
        limit=5,
        priority=2  # Lower priority (runs after task1)
    )
    
    print(f"Added tasks: {task1[:8]}, {task2[:8]}")
    
    # Run all (blocks until done, shows progress)
    manager.run_all()
    
    # Get results
    papers1 = manager.get_results(task1)
    papers2 = manager.get_results(task2)
    
    print(f"\nTask 1: {len(papers1)} papers")
    print(f"Task 2: {len(papers2)} papers")
    
    return papers1, papers2


def example_2_batch():
    """Add multiple searches at once."""
    print("\n=== Example 2: Batch Searches ===")
    
    manager = SearchQueueManager(num_workers=3)
    
    # Define searches
    searches = [
        {
            "source": "openalex",
            "query": "transfer learning",
            "limit": 10,
            "priority": 1,
        },
        {
            "source": "openalex",
            "query": "few-shot learning",
            "limit": 10,
            "priority": 1,
        },
        {
            "source": "arxiv",
            "query": "meta-learning",
            "limit": 5,
            "priority": 2,
        },
    ]
    
    # Add all at once
    task_ids = manager.add_multiple_searches(searches)
    print(f"Added {len(task_ids)} searches")
    
    # Run
    manager.run_all(show_progress=True)
    
    # Get all results
    all_results = manager.get_all_results()
    total_papers = sum(len(papers) for papers in all_results.values())
    print(f"\nTotal papers: {total_papers}")
    
    return all_results


def example_3_with_dates():
    """Advanced usage with date filtering and cache resume."""
    print("\n=== Example 3: Date Filtering ===")
    
    manager = SearchQueueManager(num_workers=2)
    
    # Add search with date range
    task_id = manager.add_search(
        source="openalex",
        query="climate change adaptation",
        start_date=date(2023, 1, 1),
        end_date=date(2024, 12, 31),
        limit=20,
        priority=0,
        resume_from_cache=True,  # Resume if interrupted
    )
    
    print(f"Added task: {task_id[:8]}")
    
    # Run (if this crashes/stops, just run again and it resumes!)
    manager.run_all()
    
    # Get results
    papers = manager.get_results(task_id)
    print(f"\nFound {len(papers)} papers on climate adaptation (2023-2024)")
    
    return papers


def example_4_context_manager():
    """Use context manager for automatic cleanup."""
    print("\n=== Example 4: Context Manager ===")
    
    with SearchQueueManager(num_workers=2) as manager:
        # Add searches
        manager.add_search("openalex", "artificial intelligence", limit=5)
        manager.add_search("arxiv", "machine learning", limit=5)
        
        # Run
        manager.run_all()
        
        # Get results
        results = manager.get_all_results()
        total = sum(len(p) for p in results.values())
        print(f"\nTotal papers: {total}")
        
        return results
    
    # Cleanup happens automatically when exiting context


def example_5_monitor_status():
    """Monitor task status during execution."""
    print("\n=== Example 5: Status Monitoring ===")
    
    manager = SearchQueueManager(num_workers=2)
    
    # Add searches
    task1 = manager.add_search("openalex", "quantum computing", limit=10)
    task2 = manager.add_search("arxiv", "deep learning", limit=5)
    
    print(f"Queue size: {manager.get_queue_size()}")
    print(f"Task 1 status: {manager.get_task_status(task1)}")
    print(f"Task 2 status: {manager.get_task_status(task2)}")
    
    # Run
    manager.run_all()
    
    # Check final status
    print(f"\nTask 1 final status: {manager.get_task_status(task1)}")
    print(f"Task 2 final status: {manager.get_task_status(task2)}")


if __name__ == "__main__":
    print("SearchQueueManager Usage Examples")
    print("=" * 50)
    
    # Run examples
    try:
        example_1_basic()
        example_2_batch()
        example_3_with_dates()
        example_4_context_manager()
        example_5_monitor_status()
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
