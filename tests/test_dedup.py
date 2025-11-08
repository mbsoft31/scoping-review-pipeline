"""Tests for deduplication logic."""

from srp.core.models import Paper, Source
from srp.dedup.deduplicator import Deduplicator


def make_paper(
    paper_id: str,
    doi: str,
    arxiv_id: str | None,
    citation_count: int,
    title: str = "Sample Title",
) -> Paper:
    """Helper to construct a simple Paper with minimal fields for testing."""
    return Paper(
        paper_id=paper_id,
        doi=doi,
        arxiv_id=arxiv_id,
        title=title,
        abstract=None,
        authors=[],
        year=2020,
        venue=None,
        fields_of_study=[],
        citation_count=citation_count,
        influential_citation_count=0,
        is_open_access=False,
        open_access_pdf=None,
        external_ids={},
        source=Source(database="test", query="", timestamp="2025-01-01T00:00:00Z"),
    )


def test_deduplicate_exact_doi() -> None:
    # Two papers with identical DOI should be merged
    p1 = make_paper("p1", "10.1234/abc", None, citation_count=5)
    p2 = make_paper("p2", "https://doi.org/10.1234/abc", None, citation_count=10)
    dedup = Deduplicator()
    deduped, clusters = dedup.deduplicate([p1, p2])
    # Should result in a single canonical paper
    assert len(deduped) == 1
    assert len(clusters) == 1
    canonical = deduped[0]
    # Canonical ID should be either p1 or p2
    assert canonical.paper_id in {"p1", "p2"}
    # Citation count should reflect the max of the two
    assert canonical.citation_count == 10


def test_deduplicate_arxiv() -> None:
    # Papers with the same arXiv ID (different versions) should be merged
    p1 = make_paper("p3", None, "1234.5678v1", citation_count=2)
    p2 = make_paper("p4", None, "arxiv:1234.5678v2", citation_count=3)
    dedup = Deduplicator()
    deduped, clusters = dedup.deduplicate([p1, p2])
    assert len(deduped) == 1
    assert len(clusters) == 1
    canonical = deduped[0]
    assert canonical.paper_id in {"p3", "p4"}
    assert canonical.citation_count == 3