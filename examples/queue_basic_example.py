#!/usr/bin/env python3
"""Basic usage examples for the improved queue system.

Demonstrates:
1. Simple single search
2. Multiple queries on one source
3. Cross-source search
4. Error handling with retries
"""

from datetime import date
from srp.async_queue import SearchQueueManager, BatchProcessor


def example_1_simple_search():
    """
    Example 1: Simple single search.
    
    This is the most basic usage - search one source with one query.
    The queue system handles all error retry and rate limiting automatically.
    """
    print("=" * 60)
    print("Example 1: Simple Search")
    print("=" * 60)
    
    # Create manager with 3 concurrent workers
    manager = SearchQueueManager(num_workers=3)
    
    # Add a search task
    task_id = manager.add_search(
        source="semantic_scholar",  # Now 5x faster!
        query="machine learning fairness",
        limit=100,
    )
    
    print(f"Added task: {task_id[:8]}")
    
    # Run all queued searches (blocks until done)
    manager.run_all()
    
    # Get results
    papers = manager.get_results(task_id)
    print(f"\nFound {len(papers)} papers")
    
    if papers:
        print("\nFirst paper:")
        print(f"  Title: {papers[0].title}")
        print(f"  Authors: {', '.join(a.name for a in papers[0].authors[:3])}")
        print(f"  Year: {papers[0].year}")


def example_2_multiple_queries():
    """
    Example 2: Search multiple queries on one source.
    
    Useful for systematic reviews where you want to search
    related concepts or query variations.
    """
    print("\n" + "=" * 60)
    print("Example 2: Multiple Queries on One Source")
    print("=" * 60)
    
    # Create batch processor
    batch = BatchProcessor(num_workers=5, deduplicate=True)
    
    # Search multiple queries
    papers = batch.search_multiple_queries(
        source="openalex",
        queries=[
            "machine learning fairness",
            "algorithmic bias detection",
            "AI equity",
        ],
        limit=200,
    )
    
    print(f"\nFound {len(papers)} unique papers (deduplicated)")
    print(f"Average papers per query: {len(papers) / 3:.1f}")


def example_3_cross_source():
    """
    Example 3: Search one query across multiple sources.
    
    Useful for comprehensive literature searches where you
    want maximum coverage.
    """
    print("\n" + "=" * 60)
    print("Example 3: Cross-Source Search")
    print("=" * 60)
    
    # Create batch processor
    batch = BatchProcessor(num_workers=5)
    
    # Search across multiple sources
    results = batch.search_across_sources(
        sources=["openalex", "semantic_scholar", "arxiv"],
        query="neural architecture search",
        limit=100,
    )
    
    print("\nResults by source:")
    for source, papers in results.items():
        print(f"  {source}: {len(papers)} papers")
    
    total = sum(len(p) for p in results.values())
    print(f"\nTotal: {total} papers")


def example_4_date_filtering():
    """
    Example 4: Search with date filtering.
    
    Limit results to a specific time period.
    """
    print("\n" + "=" * 60)
    print("Example 4: Date Filtering")
    print("=" * 60)
    
    manager = SearchQueueManager(num_workers=3)
    
    # Search only papers from 2020-2023
    task_id = manager.add_search(
        source="openalex",
        query="transformer models",
        start_date=date(2020, 1, 1),
        end_date=date(2023, 12, 31),
        limit=150,
    )
    
    manager.run_all()
    papers = manager.get_results(task_id)
    
    print(f"\nFound {len(papers)} papers from 2020-2023")
    
    # Check year distribution
    if papers:
        years = [p.year for p in papers if p.year]
        print(f"Year range: {min(years)} - {max(years)}")


def example_5_error_recovery():
    """
    Example 5: Automatic error recovery.
    
    The queue system automatically handles:
    - Rate limiting (429 errors) with backoff
    - Network errors with retry
    - API errors with intelligent retry
    - Circuit breakers to prevent cascading failures
    
    You don't need to do anything - it just works!
    """
    print("\n" + "=" * 60)
    print("Example 5: Automatic Error Recovery")
    print("=" * 60)
    
    manager = SearchQueueManager(num_workers=3)
    
    # Add multiple searches - some might hit rate limits
    task_ids = []
    for i in range(5):
        task_id = manager.add_search(
            source="semantic_scholar",
            query=f"test query {i}",
            limit=50,
        )
        task_ids.append(task_id)
    
    print(f"Added {len(task_ids)} searches")
    print("The queue will automatically:")
    print("  - Respect rate limits")
    print("  - Retry on errors")
    print("  - Back off when rate limited")
    print("  - Use circuit breakers if service fails")
    
    # Run with progress display
    manager.run_all(show_progress=True)
    
    # Check results
    all_results = manager.get_all_results()
    successful = sum(1 for papers in all_results.values() if papers)
    print(f"\n{successful}/{len(task_ids)} searches completed successfully")


def example_6_matrix_search():
    """
    Example 6: Matrix search (all combinations).
    
    Search multiple queries across multiple sources.
    Useful for comprehensive systematic reviews.
    """
    print("\n" + "=" * 60)
    print("Example 6: Matrix Search")
    print("=" * 60)
    
    batch = BatchProcessor(num_workers=5)
    
    # Search all combinations
    results = batch.search_matrix(
        sources=["openalex", "arxiv"],
        queries=["AI fairness", "ML bias"],
        limit=50,
    )
    
    print("\nResults matrix:")
    print(f"{'Source':<15} {'Query':<20} {'Papers':<10}")
    print("-" * 45)
    
    for source, queries in results.items():
        for query, papers in queries.items():
            print(f"{source:<15} {query:<20} {len(papers):<10}")
    
    total = sum(
        len(p) for source_results in results.values() 
        for p in source_results.values()
    )
    print(f"\nTotal: {total} papers")


if __name__ == "__main__":
    # Run all examples
    # Comment out any you don't want to run
    
    example_1_simple_search()
    example_2_multiple_queries()
    example_3_cross_source()
    example_4_date_filtering()
    example_5_error_recovery()
    example_6_matrix_search()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)
