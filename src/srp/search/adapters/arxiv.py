"""arXiv API adapter with category-based search and XML parsing.

This module defines an asynchronous client for the arXiv API, which returns
Atom feeds. The client supports category filtering, simple keyword queries,
pagination via `start` and `max_results`, and converts entries into the
internal `Paper` model. It respects arXiv's polite usage guidelines (roughly
one request every three seconds) and retries on service unavailability.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import AsyncIterable, Optional, Dict, Any, List
import xml.etree.ElementTree as ET

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ...config.settings import settings
from ...core.models import Paper, Author, Source
from ...core.ids import generate_paper_id, normalize_arxiv_id
from ...core.normalization import parse_date, extract_year, clean_abstract
from ..base import SearchClient
from ...utils.rate_limit import RateLimiter
from ...utils.logging import get_logger


logger = get_logger(__name__)


class ArxivClient(SearchClient):
    """
    arXiv API client with category filtering and XML parsing.

    Features:
    - Query syntax: combine categories (e.g., cs.AI) with free‑text terms.
    - Pagination via `start` and `max_results` parameters.
    - Atom XML parsing for entries, authors, dates, categories, DOIs, and PDF links.
    - Retries on HTTP 503 errors using tenacity.
    """

    BASE_URL = "http://export.arxiv.org/api/query"

    # XML namespaces
    NAMESPACES = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config or {})
        # arXiv requests: no more than one request every ~3 seconds.
        self.rate_limiter = RateLimiter(rate=0.33, period=1.0)
        self.client = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )
        self._pages_fetched = 0
        self._papers_fetched = 0

    def _build_query_string(self, query: str, categories: Optional[List[str]] = None) -> str:
        """Combine categories with the free‑text query."""
        if categories:
            cat_query = " OR ".join([f"cat:{cat}" for cat in categories])
            if query:
                return f"({cat_query}) AND ({query})"
            return cat_query
        return query

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=120),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _fetch_page(self, query: str, start: int = 0, max_results: int = 100) -> str:
        """Fetch a single page of results from arXiv (returns XML text)."""
        params = {
            "search_query": query,
            "start": start,
            "max_results": min(max_results, 2000),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        await self.rate_limiter.acquire()
        logger.debug(
            "Fetching arXiv page",
            extra={"query": query, "start": start, "max_results": max_results},
        )
        response = await self.client.get(self.BASE_URL, params=params)
        if response.status_code == 503:
            logger.warning("arXiv service unavailable (503), retrying...")
            await asyncio.sleep(5)
            raise httpx.HTTPStatusError(
                "Service unavailable", request=response.request, response=response
            )
        response.raise_for_status()
        return response.text

    def _parse_author(self, author_elem: ET.Element) -> Author:
        """Parse an <author> element into an Author model."""
        name_elem = author_elem.find("atom:name", self.NAMESPACES)
        name = name_elem.text.strip() if name_elem is not None and name_elem.text else "Unknown"
        return Author(name=name)

    def _parse_categories(self, entry: ET.Element) -> List[str]:
        """Extract primary and secondary categories from an entry."""
        categories: List[str] = []
        # Primary category
        for cat_elem in entry.findall("arxiv:primary_category", self.NAMESPACES):
            term = cat_elem.get("term")
            if term:
                categories.append(term)
        # Secondary categories
        for cat_elem in entry.findall("atom:category", self.NAMESPACES):
            term = cat_elem.get("term")
            if term and term not in categories:
                categories.append(term)
        return categories

    def _parse_entry(self, entry: ET.Element, query: str) -> Paper:
        """Convert an Atom entry into a Paper object."""
        # ID and arXiv ID
        id_elem = entry.find("atom:id", self.NAMESPACES)
        paper_url = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
        arxiv_id = normalize_arxiv_id(paper_url.split("/")[-1])
        # Title
        title_elem = entry.find("atom:title", self.NAMESPACES)
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else "Untitled"
        # Abstract
        summary_elem = entry.find("atom:summary", self.NAMESPACES)
        abstract = clean_abstract(summary_elem.text) if summary_elem is not None and summary_elem.text else None
        # Authors
        authors = [self._parse_author(a) for a in entry.findall("atom:author", self.NAMESPACES)]
        # Published date
        pub_date = None
        published_elem = entry.find("atom:published", self.NAMESPACES)
        if published_elem is not None and published_elem.text:
            try:
                pub_date = parse_date(published_elem.text[:10])  # YYYY-MM-DD
            except Exception:
                pub_date = None
        year = extract_year(pub_date)
        # Categories
        categories = self._parse_categories(entry)
        # PDF link
        pdf_link = None
        for link_elem in entry.findall("atom:link", self.NAMESPACES):
            if link_elem.get("title") == "pdf":
                pdf_link = link_elem.get("href")
                break
        # DOI (if present)
        doi = None
        doi_elem = entry.find("arxiv:doi", self.NAMESPACES)
        if doi_elem is not None and doi_elem.text:
            doi = doi_elem.text.strip()
        paper = Paper(
            paper_id=generate_paper_id("arxiv", arxiv_id),
            doi=doi,
            arxiv_id=arxiv_id,
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            publication_date=pub_date,
            venue="arXiv",
            fields_of_study=categories,
            citation_count=0,
            is_open_access=True,
            open_access_pdf=pdf_link,
            external_ids={"arxiv": arxiv_id, **({"doi": doi} if doi else {})},
            source=Source(
                database="arxiv",
                query=query,
                timestamp=datetime.utcnow().isoformat(),
            ),
        )
        return paper

    async def search(
        self,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        page: Optional[int] = None,
    ) -> AsyncIterable[Paper]:
        """Search arXiv using start/max_results pagination.

        Yields `Paper` objects. arXiv does not support date filtering directly, so
        results are filtered post‑retrieval using the provided date range.
        """
        max_results = self.config.get("max_results", 100)
        start_index = (page * max_results) if page else 0
        yielded = 0
        categories = self.config.get("categories")
        search_query = self._build_query_string(query, categories)
        logger.info(
            "Starting arXiv search",
            extra={"query": search_query, "limit": limit},
        )
        while True:
            try:
                xml_text = await self._fetch_page(
                    query=search_query,
                    start=start_index,
                    max_results=max_results,
                )
                # Parse XML
                root = ET.fromstring(xml_text)
                # total results
                total_elem = root.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
                total_results = int(total_elem.text) if total_elem is not None and total_elem.text else 0
                entries = root.findall("atom:entry", self.NAMESPACES)
                self._pages_fetched += 1
                logger.debug(
                    "Fetched arXiv page",
                    extra={"results_count": len(entries), "start": start_index, "total": total_results},
                )
                if not entries:
                    logger.info("No more results")
                    break
                for entry in entries:
                    try:
                        paper = self._parse_entry(entry, search_query)
                        # Post retrieval date filtering
                        if start_date and paper.publication_date:
                            if paper.publication_date < start_date:
                                continue
                        if end_date and paper.publication_date:
                            if paper.publication_date > end_date:
                                continue
                        self._papers_fetched += 1
                        yielded += 1
                        yield paper
                        if limit and yielded >= limit:
                            logger.info(f"Reached limit of {limit} papers")
                            return
                    except Exception as e:
                        logger.warning(f"Failed to parse entry: {e}")
                        continue
                start_index += len(entries)
                if start_index >= total_results:
                    logger.info("Reached end of results")
                    break
            except Exception as e:
                logger.error(f"Error during arXiv search: {e}")
                logger.info(f"Preserved {yielded} papers before error")
                raise
        logger.info(
            "arXiv search completed",
            extra={"total_papers": yielded, "pages_fetched": self._pages_fetched},
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "ArxivClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()