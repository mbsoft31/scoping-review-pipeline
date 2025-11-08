"""OpenAlex search adapter with cursor pagination and rate limiting."""

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
from ...core.ids import generate_paper_id, normalize_doi
from ...core.normalization import parse_date, extract_year, clean_abstract
from ..base import SearchClient
from ...utils.rate_limit import RateLimiter
from ...utils.logging import get_logger

logger = get_logger(__name__)


class OpenAlexClient(SearchClient):
    """OpenAlex API client with robust error handling and pagination."""

    BASE_URL = "https://api.openalex.org/works"

    def __init__(self, config: Optional[dict] = None) -> None:
        super().__init__(config or {})
        self.email = settings.openalex_email
        self.rate_limiter = RateLimiter(rate=settings.openalex_rate_limit, period=1.0)
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers=self._build_headers(),
        )
        self._pages_fetched = 0
        self._papers_fetched = 0

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "User-Agent": f"SystematicReviewPipeline/0.1.0 (mailto:{self.email})"
            if self.email
            else "SystematicReviewPipeline/0.1.0"
        }
        return headers

    def _build_filters(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[str]:
        filters: List[str] = []
        if start_date:
            filters.append(f"from_publication_date:{start_date.isoformat()}")
        if end_date:
            filters.append(f"to_publication_date:{end_date.isoformat()}")
        return filters

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
        reraise=True,
    )
    async def _fetch_page(
        self,
        query: str,
        filters: List[str],
        cursor: Optional[str] = None,
        per_page: int = 100,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "search": query,
            "per_page": min(per_page, 200),
        }
        if filters:
            params["filter"] = ",".join(filters)
        if cursor:
            params["cursor"] = cursor
        await self.rate_limiter.acquire()
        logger.debug("Fetching OpenAlex page", extra={"query": query, "cursor": cursor, "filters": filters})
        response = await self.client.get(self.BASE_URL, params=params)
        response.raise_for_status()
        return response.json()

    def _parse_author(self, author_data: Dict[str, Any]) -> Author:
        return Author(
            name=author_data.get("author", {}).get("display_name", "Unknown"),
            author_id=author_data.get("author", {}).get("id"),
            orcid=author_data.get("author", {}).get("orcid"),
            affiliation=author_data.get("institutions", [{}])[0].get("display_name")
            if author_data.get("institutions")
            else None,
        )

    def _reconstruct_abstract(self, inverted_index: Optional[Dict[str, List[int]]]) -> Optional[str]:
        if not inverted_index:
            return None
        try:
            words: List[tuple[int, str]] = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    words.append((pos, word))
            words.sort(key=lambda x: x[0])
            abstract = " ".join(word for _, word in words)
            return clean_abstract(abstract)
        except Exception as e:
            logger.warning(f"Failed to reconstruct abstract: {e}")
            return None

    def _parse_paper(self, work: Dict[str, Any], query: str) -> Paper:
        openalex_id = work.get("id", "").split("/")[-1]
        doi = work.get("doi", "").replace("https://doi.org/", "") if work.get("doi") else None
        pub_date = parse_date(work.get("publication_date"))
        pub_year = extract_year(pub_date) or work.get("publication_year")
        authors = [self._parse_author(a) for a in work.get("authorships", [])]
        abstract = self._reconstruct_abstract(work.get("abstract_inverted_index"))
        oa_info = work.get("open_access", {})
        is_oa = oa_info.get("is_oa", False)
        oa_url = oa_info.get("oa_url")
        primary_location = work.get("primary_location", {})
        venue = None
        if primary_location:
            source_data = primary_location.get("source", {})
            venue = source_data.get("display_name") if source_data else None
        fields = [
            concept.get("display_name")
            for concept in work.get("concepts", [])
            if concept.get("score", 0) > 0.3
        ]
        paper = Paper(
            paper_id=generate_paper_id("openalex", openalex_id),
            doi=normalize_doi(doi),
            arxiv_id=None,
            title=work.get("title", "Untitled"),
            abstract=abstract,
            authors=authors,
            year=pub_year,
            publication_date=pub_date,
            venue=venue,
            publisher=primary_location.get("source", {}).get("host_organization_name"),
            fields_of_study=fields,
            citation_count=work.get("cited_by_count", 0),
            reference_count=work.get("referenced_works_count", 0),
            is_open_access=is_oa,
            open_access_pdf=oa_url if is_oa else None,
            external_ids={"openalex": openalex_id, **({"doi": doi} if doi else {})},
            source=Source(database="openalex", query=query, timestamp=datetime.utcnow().isoformat()),
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
        filters = self._build_filters(start_date, end_date)
        per_page = self.config.get("per_page", settings.default_page_size)
        current_cursor = cursor
        papers_yielded = 0
        logger.info("Starting OpenAlex search", extra={"query": query, "start_date": start_date, "end_date": end_date, "limit": limit})
        while True:
            try:
                data = await self._fetch_page(query=query, filters=filters, cursor=current_cursor, per_page=per_page)
                meta = data.get("meta", {})
                results = data.get("results", [])
                self._pages_fetched += 1
                logger.debug("Fetched page", extra={"results_count": len(results), "cursor": current_cursor})
                for work in results:
                    try:
                        paper = self._parse_paper(work, query)
                        self._papers_fetched += 1
                        papers_yielded += 1
                        yield paper
                        if limit and papers_yielded >= limit:
                            logger.info(f"Reached limit of {limit} papers")
                            return
                    except Exception as e:
                        logger.warning(f"Failed to parse paper: {e}", extra={"work_id": work.get("id")})
                        continue
                next_cursor = meta.get("next_cursor")
                if not next_cursor:
                    logger.info("No more pages available")
                    break
                current_cursor = next_cursor
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Rate limit hit, backing off...")
                    await asyncio.sleep(5)
                    continue
                else:
                    logger.error(f"HTTP error: {e.response.status_code}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error during search: {e}")
                raise
        logger.info("Search completed", extra={"total_papers": papers_yielded, "pages_fetched": self._pages_fetched})

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()