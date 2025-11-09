"""Batch processing utilities for multiple queries and sources."""

from typing import List, Dict, Any, Optional, Set
from datetime import date
from pathlib import Path

from .manager import SearchQueueManager
from ..core.models import Paper
from ..utils.logging import get_logger

logger = get_logger(__name__)


class BatchProcessor:
    """
    Batch processing for multiple queries and sources.
    
    Provides convenient methods for common batch operations:
    - Search multiple queries across one source
    - Search one query across multiple sources
    - Search multiple queries across multiple sources
    - Automatic deduplication
    
    Example:
        >>> batch = BatchProcessor(num_workers=5)
        >>> results = batch.search_multiple_queries(
        ...     source="openalex",
        ...     queries=["AI fairness", "ML bias", "algorithmic equity"],
        ...     limit=500
        ... )
        >>> print(f"Found {len(results)} unique papers")
    """
    
    def __init__(
        self,
        num_workers: int = 3,
        cache_dir: Optional[Path] = None,
        deduplicate: bool = True,
    ):
        """
        Initialize batch processor.
        
        Args:
            num_workers: Number of concurrent workers (default: 3)
            cache_dir: Directory for cache (default: .cache)
            deduplicate: Whether to deduplicate results (default: True)
        """
        self.num_workers = num_workers
        self.cache_dir = cache_dir
        self.deduplicate = deduplicate
        self.manager = SearchQueueManager(
            num_workers=num_workers,
            cache_dir=cache_dir
        )
    
    def search_multiple_queries(
        self,
        source: str,
        queries: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> List[Paper]:
        """
        Search multiple queries on one source.
        
        Useful for systematic reviews where you want to search
        variations of the same topic or related concepts.
        
        Args:
            source: Database to search ("openalex", "arxiv", etc.)
            queries: List of query strings
            start_date: Filter papers from this date (inclusive)
            end_date: Filter papers until this date (inclusive)
            limit: Max papers per query (None = unlimited)
            
        Returns:
            Combined list of papers (deduplicated if enabled)
            
        Example:
            >>> batch = BatchProcessor()
            >>> papers = batch.search_multiple_queries(
            ...     source="openalex",
            ...     queries=[
            ...         "machine learning fairness",
            ...         "algorithmic bias detection",
            ...         "AI equity"
            ...     ],
            ...     limit=300
            ... )
        """
        logger.info(f"Batch search: {len(queries)} queries on {source}")
        
        # Add all searches with priority to maintain order
        task_ids = []
        for i, query in enumerate(queries):
            task_id = self.manager.add_search(
                source=source,
                query=query,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                priority=i,  # Maintain order
            )
            task_ids.append(task_id)
        
        # Execute all searches
        self.manager.run_all()
        
        # Collect results
        all_papers: List[Paper] = []
        for task_id in task_ids:
            papers = self.manager.get_results(task_id)
            if papers:
                all_papers.extend(papers)
        
        # Deduplicate if enabled
        if self.deduplicate:
            all_papers = self._deduplicate(all_papers)
        
        logger.info(
            f"Batch complete: {len(all_papers)} unique papers from {len(queries)} queries"
        )
        return all_papers
    
    def search_across_sources(
        self,
        sources: List[str],
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, List[Paper]]:
        """
        Search one query across multiple sources.
        
        Useful for comprehensive literature searches where you want
        to query multiple databases with the same search terms.
        
        Args:
            sources: List of databases to search
            query: Search query string
            start_date: Filter papers from this date (inclusive)
            end_date: Filter papers until this date (inclusive)
            limit: Max papers per source (None = unlimited)
            
        Returns:
            Dict mapping source name -> list of papers
            
        Example:
            >>> batch = BatchProcessor()
            >>> results = batch.search_across_sources(
            ...     sources=["openalex", "arxiv", "semantic_scholar"],
            ...     query="neural architecture search",
            ...     limit=200
            ... )
            >>> for source, papers in results.items():
            ...     print(f"{source}: {len(papers)} papers")
        """
        logger.info(f"Cross-source search: '{query}' on {len(sources)} sources")
        
        # Add searches for each source
        task_map = {}
        for i, source in enumerate(sources):
            task_id = self.manager.add_search(
                source=source,
                query=query,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                priority=i,
            )
            task_map[task_id] = source
        
        # Execute all searches
        self.manager.run_all()
        
        # Collect results by source
        results = {}
        for task_id, source in task_map.items():
            papers = self.manager.get_results(task_id)
            results[source] = papers or []
        
        total_papers = sum(len(p) for p in results.values())
        logger.info(
            f"Cross-source complete: {total_papers} papers from {len(sources)} sources"
        )
        return results
    
    def search_matrix(
        self,
        sources: List[str],
        queries: List[str],
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Dict[str, List[Paper]]]:
        """
        Search multiple queries across multiple sources (Cartesian product).
        
        Creates a matrix of all query-source combinations. Useful for
        comprehensive systematic reviews.
        
        Args:
            sources: List of databases to search
            queries: List of query strings
            start_date: Filter papers from this date
            end_date: Filter papers until this date
            limit: Max papers per query-source combination
            
        Returns:
            Nested dict: source -> query -> papers
            
        Example:
            >>> batch = BatchProcessor()
            >>> results = batch.search_matrix(
            ...     sources=["openalex", "arxiv"],
            ...     queries=["AI fairness", "ML bias"],
            ...     limit=100
            ... )
            >>> # Results:
            >>> # {"openalex": {"AI fairness": [...], "ML bias": [...]},
            >>> #  "arxiv": {"AI fairness": [...], "ML bias": [...]}}
        """
        logger.info(
            f"Matrix search: {len(queries)} queries × {len(sources)} sources "
            f"= {len(queries) * len(sources)} searches"
        )
        
        # Add all query-source combinations
        task_map = {}
        priority = 0
        for source in sources:
            for query in queries:
                task_id = self.manager.add_search(
                    source=source,
                    query=query,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    priority=priority,
                )
                task_map[task_id] = (source, query)
                priority += 1
        
        # Execute all searches
        self.manager.run_all()
        
        # Collect results in nested dict
        results: Dict[str, Dict[str, List[Paper]]] = {}
        for task_id, (source, query) in task_map.items():
            papers = self.manager.get_results(task_id) or []
            if source not in results:
                results[source] = {}
            results[source][query] = papers
        
        total_papers = sum(
            len(p) for source_results in results.values() 
            for p in source_results.values()
        )
        logger.info(f"Matrix complete: {total_papers} total papers")
        return results
    
    def _deduplicate(self, papers: List[Paper]) -> List[Paper]:
        """
        Simple deduplication by DOI and title.
        
        Uses DOI as primary key (exact match), falls back to
        normalized title (case-insensitive, stripped).
        
        Args:
            papers: List of papers to deduplicate
            
        Returns:
            Deduplicated list of papers
        """
        seen: Set[str] = set()
        unique_papers: List[Paper] = []
        
        for paper in papers:
            # Check DOI first (most reliable)
            if paper.doi:
                key = f"doi:{paper.doi.lower()}"
                if key in seen:
                    continue
                seen.add(key)
            
            # Check title (fallback for papers without DOI)
            title_key = f"title:{paper.title.lower().strip()}"
            if title_key in seen:
                continue
            seen.add(title_key)
            
            unique_papers.append(paper)
        
        removed = len(papers) - len(unique_papers)
        if removed > 0:
            logger.info(
                f"Deduplication: removed {removed} duplicates "
                f"({len(unique_papers)}/{len(papers)} unique)"
            )
        
        return unique_papers


# Convenience functions for simple usage

def search_multiple_queries(
    source: str,
    queries: List[str],
    num_workers: int = 3,
    **kwargs
) -> List[Paper]:
    """
    Convenience function for batch query search.
    
    Args:
        source: Database to search
        queries: List of query strings
        num_workers: Number of concurrent workers
        **kwargs: Additional arguments (start_date, end_date, limit)
    
    Returns:
        Combined deduplicated list of papers
    
    Example:
        >>> from srp.async_queue.batch import search_multiple_queries
        >>> papers = search_multiple_queries(
        ...     source="openalex",
        ...     queries=["AI fairness", "ML bias"],
        ...     num_workers=5,
        ...     limit=500
        ... )
        >>> print(f"Found {len(papers)} papers")
    """
    batch = BatchProcessor(num_workers=num_workers)
    return batch.search_multiple_queries(source, queries, **kwargs)


def search_across_sources(
    sources: List[str],
    query: str,
    num_workers: int = 3,
    **kwargs
) -> Dict[str, List[Paper]]:
    """
    Convenience function for cross-source search.
    
    Args:
        sources: List of databases to search
        query: Search query string
        num_workers: Number of concurrent workers
        **kwargs: Additional arguments (start_date, end_date, limit)
    
    Returns:
        Dict mapping source -> papers
    
    Example:
        >>> from srp.async_queue.batch import search_across_sources
        >>> results = search_across_sources(
        ...     sources=["openalex", "arxiv", "semantic_scholar"],
        ...     query="transformer models",
        ...     num_workers=5,
        ...     limit=200
        ... )
        >>> for source, papers in results.items():
        ...     print(f"{source}: {len(papers)} papers")
    """
    batch = BatchProcessor(num_workers=num_workers)
    return batch.search_across_sources(sources, query, **kwargs)
