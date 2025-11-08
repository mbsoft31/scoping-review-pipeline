"""Multi-strategy deduplication for academic papers."""

from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict
from rapidfuzz import fuzz

from ..core.models import Paper, DeduplicationCluster
from ..core.ids import normalize_doi, normalize_arxiv_id, compute_title_hash
from ..core.normalization import normalize_title
from ..utils.logging import get_logger

logger = get_logger(__name__)


class Deduplicator:
    """
    Multi-pass deduplication using DOI, arXiv ID, and fuzzy title matching.

    Strategy:
    1. Exact DOI match (highest confidence)
    2. Exact arXiv ID match
    3. Fuzzy title + year match (configurable threshold)
    """

    def __init__(self, fuzzy_threshold: float = 0.85, merge_strategy: str = "best_completeness") -> None:
        self.fuzzy_threshold = fuzzy_threshold
        self.merge_strategy = merge_strategy
        self._clusters: List[DeduplicationCluster] = []
        self._paper_to_canonical: Dict[str, str] = {}

    def _compute_completeness_score(self, paper: Paper) -> float:
        score = 0.0
        if paper.doi:
            score += 10
        if paper.arxiv_id:
            score += 5
        if paper.abstract:
            score += 5
        if paper.authors:
            score += 2
        if paper.venue:
            score += 2
        if paper.publication_date:
            score += 1
        if paper.is_open_access and paper.open_access_pdf:
            score += 3
        score += len(paper.fields_of_study) * 0.5
        score += min(len(paper.authors), 10) * 0.5
        return score

    def _select_canonical(self, papers: List[Paper]) -> Paper:
        if self.merge_strategy == "most_citations":
            return max(papers, key=lambda p: p.citation_count)
        if self.merge_strategy == "best_completeness":
            return max(papers, key=self._compute_completeness_score)
        return papers[0]

    def _merge_paper_data(self, canonical: Paper, duplicates: List[Paper]) -> Paper:
        merged_external_ids = dict(canonical.external_ids)
        for dup in duplicates:
            merged_external_ids.update(dup.external_ids)
        oa_pdf = canonical.open_access_pdf
        if not oa_pdf:
            for dup in duplicates:
                if dup.open_access_pdf:
                    oa_pdf = dup.open_access_pdf
                    break
        merged_fields = set(canonical.fields_of_study)
        for dup in duplicates:
            merged_fields.update(dup.fields_of_study)
        max_citations = max([p.citation_count for p in [canonical] + duplicates])
        max_influential = max([p.influential_citation_count for p in [canonical] + duplicates])
        merged = canonical.model_copy(deep=True)
        merged.external_ids = merged_external_ids
        merged.open_access_pdf = oa_pdf
        merged.fields_of_study = sorted(list(merged_fields))
        merged.citation_count = max_citations
        merged.influential_citation_count = max_influential
        return merged

    def deduplicate(self, papers: List[Paper]) -> Tuple[List[Paper], List[DeduplicationCluster]]:
        logger.info(f"Starting deduplication of {len(papers)} papers")
        matched_ids: Set[str] = set()
        clusters: List[DeduplicationCluster] = []
        papers_by_id = {p.paper_id: p for p in papers}
        # Pass 1: exact DOI
        doi_groups: Dict[str, List[str]] = defaultdict(list)
        for paper in papers:
            if paper.doi:
                doi_groups[paper.doi].append(paper.paper_id)
        for doi, paper_ids in doi_groups.items():
            if len(paper_ids) > 1:
                cluster = DeduplicationCluster(
                    canonical_id=paper_ids[0],
                    duplicate_ids=paper_ids[1:],
                    match_type="doi",
                    confidence=1.0,
                )
                clusters.append(cluster)
                matched_ids.update(paper_ids)
        logger.info(f"DOI matching: {len(clusters)} clusters, {len(matched_ids)} papers")
        # Pass 2: exact arxiv
        arxiv_groups: Dict[str, List[str]] = defaultdict(list)
        for paper in papers:
            if paper.paper_id not in matched_ids and paper.arxiv_id:
                arxiv_groups[paper.arxiv_id].append(paper.paper_id)
        for arxiv_id, paper_ids in arxiv_groups.items():
            if len(paper_ids) > 1:
                cluster = DeduplicationCluster(
                    canonical_id=paper_ids[0],
                    duplicate_ids=paper_ids[1:],
                    match_type="arxiv",
                    confidence=1.0,
                )
                clusters.append(cluster)
                matched_ids.update(paper_ids)
        logger.info(f"ArXiv matching: {len(clusters)} total clusters, {len(matched_ids)} matched papers")
        # Pass 3: fuzzy title + year
        unmatched_papers = [p for p in papers if p.paper_id not in matched_ids]
        by_year: Dict[Optional[int], List[Paper]] = defaultdict(list)
        for paper in unmatched_papers:
            by_year[paper.year].append(paper)
        fuzzy_matches = 0
        for year, year_papers in by_year.items():
            if not year or len(year_papers) < 2:
                continue
            normalized_titles: Dict[str, str] = {p.paper_id: normalize_title(p.title) for p in year_papers}
            for i, paper1 in enumerate(year_papers):
                if paper1.paper_id in matched_ids:
                    continue
                for paper2 in year_papers[i + 1 :]:
                    if paper2.paper_id in matched_ids:
                        continue
                    title1 = normalized_titles[paper1.paper_id]
                    title2 = normalized_titles[paper2.paper_id]
                    if not title1 or not title2:
                        continue
                    similarity = fuzz.ratio(title1, title2) / 100.0
                    if similarity >= self.fuzzy_threshold:
                        cluster = DeduplicationCluster(
                            canonical_id=paper1.paper_id,
                            duplicate_ids=[paper2.paper_id],
                            match_type="title_fuzzy",
                            confidence=similarity,
                        )
                        clusters.append(cluster)
                        matched_ids.update([paper1.paper_id, paper2.paper_id])
                        fuzzy_matches += 1
        logger.info(f"Fuzzy matching: {fuzzy_matches} new clusters, {len(matched_ids)} total matched")
        canonical_papers: List[Paper] = []
        for cluster in clusters:
            all_ids = [cluster.canonical_id] + cluster.duplicate_ids
            cluster_papers = [papers_by_id[pid] for pid in all_ids if pid in papers_by_id]
            canonical = self._select_canonical(cluster_papers)
            cluster.canonical_id = canonical.paper_id
            duplicates = [p for p in cluster_papers if p.paper_id != canonical.paper_id]
            merged = self._merge_paper_data(canonical, duplicates)
            canonical_papers.append(merged)
            for paper_id in all_ids:
                self._paper_to_canonical[paper_id] = canonical.paper_id
        unmatched = [p for p in papers if p.paper_id not in matched_ids]
        canonical_papers.extend(unmatched)
        for paper in unmatched:
            self._paper_to_canonical[paper.paper_id] = paper.paper_id
        logger.info(f"Deduplication complete: {len(papers)} -> {len(canonical_papers)} papers")
        logger.info(f"Removed {len(papers) - len(canonical_papers)} duplicates in {len(clusters)} clusters")
        return canonical_papers, clusters

    def get_canonical_id(self, paper_id: str) -> str:
        return self._paper_to_canonical.get(paper_id, paper_id)