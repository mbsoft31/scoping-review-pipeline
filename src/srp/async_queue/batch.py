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
            num_workers: Number of concurrent workers
            cache_dir: Directory for caching results
            deduplicate: Whether to deduplicate results automatically
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
        
        Useful for systematic reviews with multiple search terms
        or different phrasings of the same concept.
        
        Args:
            source: Database to search ("openalex", "arxiv", etc.)
            queries: List of query strings
            start_date: Filter papers from this date
            end_date: Filter papers until this date
            limit: Max papers per query
            
        Returns:
            Combined list of papers (deduplicated if enabled)
            
        Example:
            >>> queries = [
            ...     "machine learning fairness",
            ...     "algorithmic bias",
            ...     "AI ethics"
            ... ]
            >>> papers = batch.search_multiple_queries(
            ...     source="openalex",
            ...     queries=queries,
            ...     limit=500
            ... )
        """
        logger.info(f"Batch search: {len(queries)} queries on {source}")
        
        # Add all searches
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
            logger.debug(f"Added query {i+1}/{len(queries)}: '{query[:50]}...'")
        
        # Execute all searches
        logger.info("Executing batch searches...")
        self.manager.run_all()
        
        # Collect results
        all_papers: List[Paper] = []
        for i, task_id in enumerate(task_ids):
            papers = self.manager.get_results(task_id)
            if papers:
                all_papers.extend(papers)
                logger.info(f"Query {i+1}: {len(papers)} papers")
            else:
                logger.warning(f"Query {i+1}: No results")
        
        # Deduplicate
        if self.deduplicate and len(all_papers) > 0:
            all_papers = self._deduplicate(all_papers)
        
        logger.info(
            f"Batch complete: {len(all_papers)} papers from {len(queries)} queries"
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
        
        Useful for comprehensive literature reviews that need
        to check multiple databases.
        
        Args:
            sources: List of databases to search
            query: Search query
            start_date: Filter papers from this date
            end_date: Filter papers until this date
            limit: Max papers per source
            
        Returns:
            Dict mapping source name -> list of papers
            
        Example:
            >>> results = batch.search_across_sources(
            ...     sources=["openalex", "arxiv", "semantic_scholar"],
            ...     query="machine learning fairness",
            ...     limit=200
            ... )
            >>> for source, papers in results.items():
            ...     print(f"{source}: {len(papers)} papers")
        """
        logger.info(f"Cross-source search: '{query}' on {len(sources)} sources")
        
        # Add searches
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
            logger.debug(f"Added source {i+1}/{len(sources)}: {source}")
        
        # Execute all searches
        logger.info("Executing cross-source searches...")
        self.manager.run_all()
        
        # Collect results by source
        results = {}
        for task_id, source in task_map.items():
            papers = self.manager.get_results(task_id)
            results[source] = papers or []
            logger.info(f"{source}: {len(results[source])} papers")
        
        total = sum(len(p) for p in results.values())
        logger.info(
            f"Cross-source complete: {total} papers from {len(sources)} sources"
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
        Search multiple queries across multiple sources.
        
        Creates a matrix of results: sources x queries.
        
        Args:
            sources: List of databases to search
            queries: List of query strings
            start_date: Filter papers from this date
            end_date: Filter papers until this date
            limit: Max papers per search
            
        Returns:
            Nested dict: source -> query -> papers
            
        Example:
            >>> results = batch.search_matrix(
            ...     sources=["openalex", "arxiv"],
            ...     queries=["AI fairness", "ML bias"],
            ...     limit=100
            ... )
            >>> for source in results:
            ...     for query in results[source]:
            ...         papers = results[source][query]
            ...         print(f"{source} / {query}: {len(papers)} papers")
        """
        logger.info(
            f"Matrix search: {len(sources)} sources x {len(queries)} queries = "
            f"{len(sources) * len(queries)} total searches"
        )
        
        # Add all searches
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
        logger.info("Executing matrix searches...")
        self.manager.run_all()
        
        # Collect results in nested dict
        results: Dict[str, Dict[str, List[Paper]]] = {}
        for task_id, (source, query) in task_map.items():
            papers = self.manager.get_results(task_id) or []
            
            if source not in results:
                results[source] = {}
            results[source][query] = papers
            
            logger.debug(f"{source} / {query[:30]}...: {len(papers)} papers")
        
        total = sum(
            len(papers)
            for source_results in results.values()
            for papers in source_results.values()
        )
        logger.info(f"Matrix complete: {total} total papers")
        return results
    
    def _deduplicate(self, papers: List[Paper]) -> List[Paper]:
        """
        Simple deduplication by DOI and title.
        
        Prefers papers with DOIs. For papers without DOIs,
        uses normalized title matching.
        
        Args:
            papers: List of papers to deduplicate
            
        Returns:
            Deduplicated list of papers
        """
        seen: Set[str] = set()
        unique_papers: List[Paper] = []
        
        # Sort to prefer papers with more metadata
        sorted_papers = sorted(
            papers,
            key=lambda p: (bool(p.doi), bool(p.abstract), p.citation_count or 0),
            reverse=True
        )
        
        for paper in sorted_papers:
            # Check DOI first (most reliable)
            if paper.doi:
                key = f"doi:{paper.doi.lower().strip()}"
                if key in seen:
                    continue
                seen.add(key)
            
            # Check arXiv ID
            if paper.arxiv_id:
                key = f"arxiv:{paper.arxiv_id.lower().strip()}"
                if key in seen:
                    continue
                seen.add(key)
            
            # Check normalized title
            if paper.title:
                title_key = f"title:{paper.title.lower().strip()}"
                if title_key in seen:
                    continue
                seen.add(title_key)
            
            unique_papers.append(paper)
        
        removed = len(papers) - len(unique_papers)
        if removed > 0:
            logger.info(
                f"Deduplicated: removed {removed} duplicates "
                f"({removed/len(papers)*100:.1f}%)"
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
        Deduplicated list of papers
        
    Example:
        >>> papers = search_multiple_queries(
        ...     source="openalex",
        ...     queries=["AI fairness", "ML bias"],
        ...     limit=500
        ... )
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
        query: Search query
        num_workers: Number of concurrent workers
        **kwargs: Additional arguments (start_date, end_date, limit)
        
    Returns:
        Dict mapping source -> papers
        
    Example:
        >>> results = search_across_sources(
        ...     sources=["openalex", "arxiv", "semantic_scholar"],
        ...     query="machine learning fairness",
        ...     limit=200
        ... )
    """
    batch = BatchProcessor(num_workers=num_workers)
    return batch.search_across_sources(sources, query, **kwargs)