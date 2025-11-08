"""Search orchestration across multiple sources with caching and resume."""

import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import date

from ..core.models import Paper
from ..io.cache import SearchCache
from ..io.paths import get_cache_path
from .base import SearchClient
from .adapters.openalex import OpenAlexClient
from .adapters.semantic_scholar import SemanticScholarClient
from .adapters.crossref import CrossrefClient  # new source
from .adapters.arxiv import ArxivClient  # new source
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SearchOrchestrator:
    """Orchestrate searches across multiple sources with caching and resumability."""

    CLIENT_MAP = {
        "openalex": OpenAlexClient,
        "semantic_scholar": SemanticScholarClient,
        "crossref": CrossrefClient,
        "arxiv": ArxivClient,
    }

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self.cache_dir = cache_dir or get_cache_path("searches")
        self.cache = SearchCache(self.cache_dir)

    async def search_source(
        self,
        source: str,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None,
        resume: bool = True,
    ) -> List[Paper]:
        if source not in self.CLIENT_MAP:
            raise ValueError(f"Unknown source: {source}. Available: {list(self.CLIENT_MAP.keys())}")
        query_id = self.cache.register_query(
            source=source,
            query=query,
            start_date=start_date.isoformat() if start_date else None,
            end_date=end_date.isoformat() if end_date else None,
        )
        progress = self.cache.get_query_progress(query_id)
        if resume and progress and progress.get("completed"):
            logger.info(f"Using cached results for query_id={query_id}")
            return self.cache.get_cached_papers(query_id)
        client_class: type[SearchClient] = self.CLIENT_MAP[source]
        papers: List[Paper] = []
        async with client_class(config or {}) as client:
            try:
                async for paper in client.search(
                    query=query,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                ):
                    papers.append(paper)
                    self.cache.cache_paper(query_id, paper)
                self.cache.mark_completed(query_id)
                logger.info(f"Search completed: {len(papers)} papers from {source}")
            except Exception as e:
                logger.error(f"Search failed for {source}: {e}")
                raise
        return papers

    async def search_all_sources(
        self,
        sources: List[str],
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit_per_source: Optional[int] = None,
        configs: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, List[Paper]]:
        configs = configs or {}
        tasks: List[tuple[str, asyncio.Future]] = []
        for source in sources:
            task = self.search_source(
                source=source,
                query=query,
                start_date=start_date,
                end_date=end_date,
                limit=limit_per_source,
                config=configs.get(source),
            )
            tasks.append((source, task))
        results: Dict[str, List[Paper]] = {}
        for source, task in tasks:
            try:
                papers = await task
                results[source] = papers
                logger.info(f"{source}: {len(papers)} papers")
            except Exception as e:
                logger.error(f"{source} failed: {e}")
                results[source] = []
        return results

    def close(self) -> None:
        self.cache.close()