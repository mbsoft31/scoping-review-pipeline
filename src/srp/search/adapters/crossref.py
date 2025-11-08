"""Crossref API adapter with polite pool and offset pagination.

This module defines an asynchronous client for the Crossref API, supporting
polite usage via a mailto email address (for increased rate limits), offset
pagination, date filtering, and parsing of Crossref works into the internal
`Paper` model. The client retries on transient HTTP errors using tenacity
with exponential backoff.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import AsyncIterable, Optional, Dict, Any, List

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ...config.settings import settings
from ...core.models import Paper, Author, Source
from ...core.ids import generate_paper_id, normalize_doi
from ...core.normalization import parse_date, extract_year, clean_abstract
from ..base import SearchClient
from ...utils.rate_limit import RateLimiter
from ...utils.logging import get_logger


logger = get_logger(__name__)


class CrossrefClient(SearchClient):
    """
    Crossref API client with polite pool access and offset pagination.

    Features:
    - Polite pool with mailto parameter (higher request rate).
    - Field selection for efficiency.
    - Date filtering with from‑pub‑date/until‑pub‑date.
    - Robust error handling and retry logic.
    """

    BASE_URL = "https://api.crossref.org/works"

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config or {})
        self.email = settings.crossref_email
        # Polite pool: if an email is provided, Crossref allows higher throughput (≈50 req/s)
        # Otherwise, fall back to configured rate limit
        self.rate_limiter = RateLimiter(
            rate=50.0 if self.email else settings.crossref_rate_limit,
            period=1.0,
        )
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers=self._build_headers(),
        )
        self._pages_fetched = 0
        self._papers_fetched = 0

    def _build_headers(self) -> Dict[str, str]:
        """Build headers with User‑Agent including email for polite pool."""
        ua = "SystematicReviewPipeline/0.1.0"
        if self.email:
            ua += f" (mailto:{self.email})"
        return {"User-Agent": ua}

    def _build_query_params(
        self,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        offset: int = 0,
        rows: int = 100,
    ) -> Dict[str, Any]:
        """Construct query parameters for Crossref request."""
        params: Dict[str, Any] = {
            "query": query,
            "offset": offset,
            # Crossref allows up to 1000 records per request
            "rows": min(rows, 1000),
            # Select only needed fields to reduce payload
            "select": ",".join(
                [
                    "DOI",
                    "title",
                    "abstract",
                    "author",
                    "published",
                    "container-title",
                    "publisher",
                    "subject",
                    "type",
                    "is-referenced-by-count",
                    "link",
                ]
            ),
        }
        filters: List[str] = []
        if start_date:
            filters.append(f"from-pub-date:{start_date.isoformat()}")
        if end_date:
            filters.append(f"until-pub-date:{end_date.isoformat()}")
        if filters:
            params["filter"] = ",".join(filters)
        return params

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _fetch_page(
        self,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        offset: int = 0,
        rows: int = 100,
    ) -> Dict[str, Any]:
        """Fetch a single page of results and return the parsed JSON."""
        params = self._build_query_params(
            query=query,
            start_date=start_date,
            end_date=end_date,
            offset=offset,
            rows=rows,
        )
        await self.rate_limiter.acquire()
        logger.debug("Fetching Crossref page", extra={"query": query, "offset": offset})
        response = await self.client.get(self.BASE_URL, params=params)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            logger.warning(f"Rate limited, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            raise httpx.HTTPStatusError(
                "Rate limited", request=response.request, response=response
            )
        response.raise_for_status()
        return response.json()

    def _parse_author(self, author_data: Dict[str, Any]) -> Author:
        """Parse an author from Crossref's JSON structure."""
        given = author_data.get("given", "")
        family = author_data.get("family", "")
        name = f"{given} {family}".strip() or "Unknown"
        affiliation = None
        aff_list = author_data.get("affiliation")
        if aff_list:
            # Affiliation is a list of dicts; take first name
            aff = aff_list[0]
            if isinstance(aff, dict):
                affiliation = aff.get("name")
        return Author(name=name, affiliation=affiliation, orcid=author_data.get("ORCID"))

    def _parse_date(self, date_parts: List[List[int]]) -> Optional[date]:
        """Convert Crossref date‑parts field ([[year, month, day]]) to a date."""
        if not date_parts or not date_parts[0]:
            return None
        parts = date_parts[0]
        try:
            year = parts[0]
            month = parts[1] if len(parts) > 1 else 1
            day = parts[2] if len(parts) > 2 else 1
            return date(year, month, day)
        except (ValueError, IndexError):
            return None

    def _parse_paper(self, work: Dict[str, Any], query: str) -> Paper:
        """Convert a Crossref work item to the internal Paper model."""
        doi = normalize_doi(work.get("DOI"))
        # Publication date and year
        published = work.get("published") or work.get("published-print") or {}
        pub_date = self._parse_date(published.get("date-parts"))
        year = extract_year(pub_date)
        # Authors
        authors_data = work.get("author", [])
        authors = [self._parse_author(a) for a in authors_data]
        # Abstract
        abstract_raw = work.get("abstract")
        abstract = clean_abstract(abstract_raw) if abstract_raw else None
        # Venue (container title)
        venue = None
        container = work.get("container-title")
        if container:
            venue = container[0] if isinstance(container, list) and container else container
        # Publisher
        publisher = work.get("publisher")
        # Fields/subjects
        fields = work.get("subject", []) or []
        # Citation count
        citation_count = work.get("is-referenced-by-count", 0) or 0
        # Type
        work_type = work.get("type", "unknown")
        # Open access PDF
        oa_pdf = None
        links = work.get("link", []) or []
        for link in links:
            if link.get("content-type") == "application/pdf":
                oa_pdf = link.get("URL")
                break
        paper = Paper(
            paper_id=generate_paper_id("crossref", doi or work.get("URL", "")),
            doi=doi,
            title=(work.get("title") or ["Untitled"])[0],
            abstract=abstract,
            authors=authors,
            year=year,
            publication_date=pub_date,
            venue=venue,
            publisher=publisher,
            fields_of_study=fields,
            citation_count=citation_count,
            is_open_access=bool(oa_pdf),
            open_access_pdf=oa_pdf,
            external_ids={"crossref": doi, **({"doi": doi} if doi else {})},
            source=Source(
                database="crossref",
                query=query,
                timestamp=datetime.utcnow().isoformat(),
            ),
            raw_data=work,
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
        """Search Crossref with offset pagination.

        Yields `Paper` objects until the specified limit or all results are retrieved.
        """
        rows = self.config.get("rows", 100)
        offset = (page * rows) if page else 0
        yielded = 0
        logger.info(
            f"Starting Crossref search",
            extra={
                "query": query,
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            },
        )
        while True:
            try:
                data = await self._fetch_page(
                    query=query,
                    start_date=start_date,
                    end_date=end_date,
                    offset=offset,
                    rows=rows,
                )
                message = data.get("message", {})
                items = message.get("items", [])
                total_results = message.get("total-results", 0)
                self._pages_fetched += 1
                logger.debug(
                    f"Fetched Crossref page {self._pages_fetched}",
                    extra={"results_count": len(items), "offset": offset, "total": total_results},
                )
                if not items:
                    logger.info("No more results")
                    break
                for work in items:
                    try:
                        paper = self._parse_paper(work, query)
                        self._papers_fetched += 1
                        yielded += 1
                        yield paper
                        if limit and yielded >= limit:
                            logger.info(f"Reached limit of {limit} papers")
                            return
                    except Exception as e:
                        logger.warning(f"Failed to parse work: {e}", extra={"doi": work.get("DOI")})
                        continue
                offset += len(items)
                if offset >= total_results:
                    logger.info("Reached end of results")
                    break
            except Exception as e:
                logger.error(f"Error during Crossref search: {e}")
                logger.info(f"Preserved {yielded} papers before error")
                raise
        logger.info(
            f"Crossref search completed",
            extra={"total_papers": yielded, "pages_fetched": self._pages_fetched},
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> "CrossrefClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()