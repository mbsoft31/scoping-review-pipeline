"""Tests for influence scoring logic."""

from srp.core.models import Paper, Source, Reference
from srp.enrich.influence import InfluenceScorer


def make_paper(paper_id: str, citation_count: int) -> Paper:
    return Paper(
        paper_id=paper_id,
        doi=None,
        arxiv_id=None,
        title=f"Paper {paper_id}",
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


def test_influence_ranking() -> None:
    # Four papers with a small citation network
    a = make_paper("A", citation_count=100)
    b = make_paper("B", citation_count=50)
    c = make_paper("C", citation_count=10)
    d = make_paper("D", citation_count=5)
    papers = [a, b, c, d]
    # References: B->A, C->A, D->C, B->C
    refs = [
        Reference(citing_paper_id="B", cited_paper_id="A", cited_doi=None, cited_title=None, source="test"),
        Reference(citing_paper_id="C", cited_paper_id="A", cited_doi=None, cited_title=None, source="test"),
        Reference(citing_paper_id="D", cited_paper_id="C", cited_doi=None, cited_title=None, source="test"),
        Reference(citing_paper_id="B", cited_paper_id="C", cited_doi=None, cited_title=None, source="test"),
    ]
    scorer = InfluenceScorer()
    df = scorer.compute_influence_scores(papers, refs)
    # The most influential paper should be A due to high citation count and being cited
    top = df.iloc[0]
    assert top["paper_id"] == "A"
    # Influence scores should be non-negative and sorted descending
    scores = df["influence_score"].values
    assert all(s >= 0 for s in scores)
    assert list(scores) == sorted(scores, reverse=True)