"""Semantic Scholar API adapter with offset pagination and special header handling."""

import asyncio
from datetime import date, datetime
from typing import AsyncIterable, Optional, Dict, Any, List
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ...config.settings import settings
from ...core.models import Paper, Author, Source
from ...core.ids import generate_paper_id, normalize_doi, normalize_arxiv_id
from ...core.normalization import parse_date, extract_year, clean_abstract
from ..base import SearchClient
from ...utils.rate_limit import RateLimiter
from ...utils.logging import get_logger

logger = get_logger(__name__)


class SemanticScholarClient(SearchClient):
    """Semantic Scholar API client with quirky header support and offset pagination."""

    BASE_URL = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config or {})
        self.api_key = settings.semantic_scholar_api_key
        self.rate_limiter = RateLimiter(rate=settings.semantic_scholar_rate_limit, period=1.0)
        self.per_page_delay = self.config.get("per_page_delay", 1.3)
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers=self._build_headers(),
        )
        self._pages_fetched = 0
        self._papers_fetched = 0

    def _build_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "SystematicReviewPipeline/0.1.0"}
        if self.api_key:
            # Strip any quotes from the API key value
            key_value = self.api_key.strip("'\"")
            headers["x-api-key"] = key_value
        return headers

    def _build_query_params(
        self,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "query": query,
            "offset": offset,
            "limit": min(limit, 100),
            "fields": ",".join(
                [
                    "paperId",
                    "externalIds",
                    "title",
                    "abstract",
                    "authors",
                    "year",
                    "publicationDate",
                    "venue",
                    "publicationTypes",
                    "citationCount",
                    "influentialCitationCount",
                    "referenceCount",
                    "isOpenAccess",
                    "openAccessPdf",
                    "fieldsOfStudy",
                ]
            ),
        }
        if start_date:
            params["year"] = f"{start_date.year}-"
        if end_date:
            if start_date:
                params["year"] = f"{start_date.year}-{end_date.year}"
            else:
                params["year"] = f"-{end_date.year}"
        return params

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _fetch_page(
        self,
        query: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        offset: int = 0,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        params = self._build_query_params(query, start_date, end_date, offset, page_size)
        await self.rate_limiter.acquire()
        logger.debug("Fetching S2 page", extra={"query": query, "offset": offset, "page_size": page_size})
        response = await self.client.get(f"{self.BASE_URL}/paper/search", params=params)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 10))
            logger.warning(f"Rate limited, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)
        response.raise_for_status()
        # Additional per-page delay to avoid S2 throttling
        if self.per_page_delay > 0:
            await asyncio.sleep(self.per_page_delay)
        return response.json()

    def _parse_author(self, author_data: Dict[str, Any]) -> Author:
        return Author(
            name=author_data.get("name", "Unknown"),
            author_id=author_data.get("authorId"),
        )

    def _parse_paper(self, paper_data: Dict[str, Any], query: str) -> Paper:
        paper_id = paper_data.get("paperId")
        external_ids = paper_data.get("externalIds", {})
        doi = normalize_doi(external_ids.get("DOI"))
        arxiv_id = normalize_arxiv_id(external_ids.get("ArXiv"))
        pub_date = parse_date(paper_data.get("publicationDate"))
        year = extract_year(pub_date) or paper_data.get("year")
        authors = [self._parse_author(a) for a in paper_data.get("authors", [])]
        oa_pdf = None
        if paper_data.get("isOpenAccess") and paper_data.get("openAccessPdf"):
            oa_pdf = paper_data["openAccessPdf"].get("url")
        paper = Paper(
            paper_id=generate_paper_id("s2", paper_id),
            doi=doi,
            arxiv_id=arxiv_id,
            title=paper_data.get("title", "Untitled"),
            abstract=clean_abstract(paper_data.get("abstract")),
            authors=authors,
            year=year,
            publication_date=pub_date,
            venue=paper_data.get("venue"),
            fields_of_study=paper_data.get("fieldsOfStudy") or [],
            citation_count=paper_data.get("citationCount", 0),
            influential_citation_count=paper_data.get("influentialCitationCount", 0),
            reference_count=paper_data.get("referenceCount", 0),
            is_open_access=paper_data.get("isOpenAccess", False),
            open_access_pdf=oa_pdf,
            external_ids={"s2": paper_id, **({"doi": doi} if doi else {}), **({"arxiv": arxiv_id} if arxiv_id else {})},
            source=Source(database="semantic_scholar", query=query, timestamp=datetime.utcnow().isoformat()),
            raw_data=paper_data,
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
        page_size = self.config.get("page_size", 20)
        offset = (page * page_size) if page else 0
        papers_yielded = 0
        logger.info("Starting S2 search", extra={"query": query, "start_date": start_date, "end_date": end_date, "limit": limit})
        while True:
            try:
                data = await self._fetch_page(query, start_date, end_date, offset, page_size)
                papers_data = data.get("data", [])
                total = data.get("total", 0)
                self._pages_fetched += 1
                logger.debug("Fetched S2 page", extra={"results_count": len(papers_data), "offset": offset, "total": total})
                if not papers_data:
                    logger.info("No more papers available")
                    break
                for paper_data in papers_data:
                    try:
                        paper = self._parse_paper(paper_data, query)
                        self._papers_fetched += 1
                        papers_yielded += 1
                        yield paper
                        if limit and papers_yielded >= limit:
                            logger.info(f"Reached limit of {limit} papers")
                            return
                    except Exception as e:
                        logger.warning(f"Failed to parse paper: {e}", extra={"paper_id": paper_data.get("paperId")})
                        continue
                offset += len(papers_data)
                if offset >= total:
                    logger.info("Reached end of results")
                    break
            except Exception as e:
                logger.error(f"Error during S2 search: {e}")
                raise
        logger.info("S2 search completed", extra={"total_papers": papers_yielded, "pages_fetched": self._pages_fetched})

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()