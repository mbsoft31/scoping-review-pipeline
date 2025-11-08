"""Citation graph construction and reference fetching."""

import asyncio
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict

from ..core.models import Paper, Reference
from ..search.adapters.openalex import OpenAlexClient
from ..search.adapters.semantic_scholar import SemanticScholarClient
from ..utils.logging import get_logger

logger = get_logger(__name__)


class CitationEnricher:
    """
    Fetch citation references and build citation network.

    Workflow:
    1. Prioritize papers by citation count
    2. Fetch references for top N papers
    3. Build DOI → paper_id mapping
    4. Resolve in-corpus citations
    """

    def __init__(self, max_papers: int = 200, refs_per_paper: int = 100) -> None:
        self.max_papers = max_papers
        self.refs_per_paper = refs_per_paper

    def _build_doi_index(self, papers: List[Paper]) -> Dict[str, str]:
        doi_index: Dict[str, str] = {}
        for paper in papers:
            if paper.doi:
                doi_index[paper.doi] = paper.paper_id
        return doi_index

    def _prioritize_papers(self, papers: List[Paper]) -> List[Paper]:
        return sorted(papers, key=lambda p: p.citation_count, reverse=True)[: self.max_papers]

    async def _fetch_references_s2(self, paper: Paper, client: SemanticScholarClient) -> List[Reference]:
        references: List[Reference] = []
        s2_id = paper.external_ids.get("s2")
        if not s2_id:
            return references
        try:
            await client.rate_limiter.acquire()
            response = await client.client.get(
                f"{client.BASE_URL}/paper/{s2_id}/references",
                params={"fields": "title,externalIds", "limit": self.refs_per_paper},
            )
            if response.status_code == 200:
                data = response.json()
                for ref in data.get("data", []):
                    cited_paper = ref.get("citedPaper", {})
                    external_ids = cited_paper.get("externalIds", {})
                    references.append(
                        Reference(
                            citing_paper_id=paper.paper_id,
                            cited_doi=external_ids.get("DOI"),
                            cited_title=cited_paper.get("title"),
                            source="semantic_scholar",
                        )
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch S2 references for {paper.paper_id}: {e}")
        return references

    async def _fetch_references_openalex(self, paper: Paper, client: OpenAlexClient) -> List[Reference]:
        references: List[Reference] = []
        openalex_id = paper.external_ids.get("openalex")
        if not openalex_id:
            return references
        try:
            await client.rate_limiter.acquire()
            response = await client.client.get(f"https://api.openalex.org/works/{openalex_id}")
            if response.status_code == 200:
                data = response.json()
                referenced_works = data.get("referenced_works", [])
                for work_id in referenced_works[: self.refs_per_paper]:
                    try:
                        await client.rate_limiter.acquire()
                        ref_response = await client.client.get(work_id)
                        if ref_response.status_code == 200:
                            ref_data = ref_response.json()
                            doi = ref_data.get("doi", "").replace("https://doi.org/", "")
                            references.append(
                                Reference(
                                    citing_paper_id=paper.paper_id,
                                    cited_doi=doi if doi else None,
                                    cited_title=ref_data.get("title"),
                                    source="openalex",
                                )
                            )
                    except Exception as e:
                        logger.debug(f"Failed to fetch reference {work_id}: {e}")
                        continue
        except Exception as e:
            logger.warning(f"Failed to fetch OpenAlex references for {paper.paper_id}: {e}")
        return references

    async def fetch_references(self, papers: List[Paper], sources: List[str] = ["semantic_scholar"]) -> List[Reference]:
        logger.info(f"Fetching references for top {self.max_papers} papers")
        prioritized = self._prioritize_papers(papers)
        all_refs: List[Reference] = []
        for source in sources:
            if source == "semantic_scholar":
                async with SemanticScholarClient() as client:
                    for i, paper in enumerate(prioritized, 1):
                        refs = await self._fetch_references_s2(paper, client)
                        all_refs.extend(refs)
                        if i % 10 == 0:
                            logger.info(f"Fetched references for {i}/{len(prioritized)} papers")
            elif source == "openalex":
                async with OpenAlexClient() as client:
                    for i, paper in enumerate(prioritized, 1):
                        refs = await self._fetch_references_openalex(paper, client)
                        all_refs.extend(refs)
                        if i % 10 == 0:
                            logger.info(f"Fetched references for {i}/{len(prioritized)} papers")
        logger.info(f"Fetched {len(all_refs)} total references")
        return all_refs

    def resolve_citations(self, references: List[Reference], papers: List[Paper]) -> Tuple[List[Reference], Dict[str, int]]:
        logger.info("Resolving citations to corpus papers")
        doi_index = self._build_doi_index(papers)
        resolved: List[Reference] = []
        in_corpus = 0
        external = 0
        for ref in references:
            resolved_ref = ref.model_copy()
            if ref.cited_doi and ref.cited_doi in doi_index:
                resolved_ref.cited_paper_id = doi_index[ref.cited_doi]
                in_corpus += 1
            else:
                external += 1
            resolved.append(resolved_ref)
        in_degree: Dict[str, int] = defaultdict(int)
        for ref in resolved:
            if ref.cited_paper_id:
                in_degree[ref.cited_paper_id] += 1
        stats = {
            "total_references": len(references),
            "in_corpus_citations": in_corpus,
            "external_citations": external,
            "cited_papers": len(in_degree),
        }
        logger.info(f"Resolved {in_corpus} in-corpus citations, {external} external")
        logger.info(f"Citation network has {len(in_degree)} cited papers")
        return resolved, stats