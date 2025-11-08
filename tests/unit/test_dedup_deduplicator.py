"""Comprehensive unit tests for deduplication logic."""

from datetime import date
import pytest

from srp.core.models import Paper, Source, Author
from srp.dedup.deduplicator import Deduplicator


def make_paper(
    paper_id: str,
    title: str = "Sample Paper",
    doi: str | None = None,
    arxiv_id: str | None = None,
    year: int | None = 2024,
    citation_count: int = 0,
    abstract: str | None = None,
    authors: list[Author] | None = None,
    venue: str | None = None,
    fields_of_study: list[str] | None = None,
    is_open_access: bool = False,
    open_access_pdf: str | None = None,
) -> Paper:
    """Helper to construct a Paper for testing."""
    return Paper(
        paper_id=paper_id,
        doi=doi,
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors or [],
        year=year,
        venue=venue,
        fields_of_study=fields_of_study or [],
        citation_count=citation_count,
        influential_citation_count=0,
        is_open_access=is_open_access,
        open_access_pdf=open_access_pdf,
        external_ids={},
        source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
    )


class TestDeduplicatorDOIMatching:
    """Tests for exact DOI matching."""

    def test_deduplicate_exact_doi_simple(self) -> None:
        """Test two papers with identical DOI are merged."""
        p1 = make_paper("p1", doi="10.1234/abc", citation_count=5)
        p2 = make_paper("p2", doi="10.1234/abc", citation_count=10)
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        assert len(deduped) == 1
        assert len(clusters) == 1
        assert clusters[0].match_type == "doi"
        assert clusters[0].confidence == 1.0

    def test_deduplicate_doi_normalization(self) -> None:
        """Test DOI normalization during deduplication."""
        p1 = make_paper("p1", doi="10.1234/abc")
        p2 = make_paper("p2", doi="https://doi.org/10.1234/ABC")
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        # Both DOIs normalize to same value, should deduplicate
        assert len(deduped) == 1
        assert len(clusters) == 1

    def test_deduplicate_multiple_doi_groups(self) -> None:
        """Test multiple DOI duplicate groups."""
        papers = [
            make_paper("p1", doi="10.1234/a"),
            make_paper("p2", doi="10.1234/a"),
            make_paper("p3", doi="10.1234/b"),
            make_paper("p4", doi="10.1234/b"),
            make_paper("p5", doi="10.1234/c"),  # Unique
        ]
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 3  # 3 unique DOIs
        assert len(clusters) == 2  # 2 duplicate groups

    def test_deduplicate_doi_max_citations(self) -> None:
        """Test canonical selection by max citations."""
        p1 = make_paper("p1", doi="10.1234/abc", citation_count=5)
        p2 = make_paper("p2", doi="10.1234/abc", citation_count=10)
        p3 = make_paper("p3", doi="10.1234/abc", citation_count=3)
        
        dedup = Deduplicator(merge_strategy="most_citations")
        deduped, clusters = dedup.deduplicate([p1, p2, p3])
        
        assert len(deduped) == 1
        assert deduped[0].citation_count == 10


class TestDeduplicatorArxivMatching:
    """Tests for exact arXiv ID matching."""

    def test_deduplicate_exact_arxiv(self) -> None:
        """Test papers with same arXiv ID are merged."""
        p1 = make_paper("p1", arxiv_id="1234.5678")
        p2 = make_paper("p2", arxiv_id="1234.5678")
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        assert len(deduped) == 1
        assert len(clusters) == 1
        assert clusters[0].match_type == "arxiv"
        assert clusters[0].confidence == 1.0

    def test_deduplicate_arxiv_version_normalization(self) -> None:
        """Test arXiv versions are normalized (v1, v2, etc.)."""
        p1 = make_paper("p1", arxiv_id="1234.5678v1")
        p2 = make_paper("p2", arxiv_id="arxiv:1234.5678v2")
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        # Should deduplicate since versions normalize to same ID
        assert len(deduped) == 1
        assert len(clusters) == 1

    def test_deduplicate_doi_takes_precedence_over_arxiv(self) -> None:
        """Test DOI matching happens before arXiv matching."""
        p1 = make_paper("p1", doi="10.1234/abc", arxiv_id="1234.5678")
        p2 = make_paper("p2", doi="10.1234/abc", arxiv_id="9999.9999")
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        # Should match on DOI, not care about different arXiv IDs
        assert len(deduped) == 1
        assert len(clusters) == 1
        assert clusters[0].match_type == "doi"

    def test_deduplicate_arxiv_only_unmatched_papers(self) -> None:
        """Test arXiv matching only applies to papers not matched by DOI."""
        papers = [
            make_paper("p1", doi="10.1234/a", arxiv_id="1111.1111"),
            make_paper("p2", doi="10.1234/a", arxiv_id="2222.2222"),  # Matches p1 by DOI
            make_paper("p3", arxiv_id="3333.3333"),
            make_paper("p4", arxiv_id="3333.3333"),  # Matches p3 by arXiv
        ]
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 2  # One DOI cluster, one arXiv cluster
        assert len(clusters) == 2


class TestDeduplicatorFuzzyTitleMatching:
    """Tests for fuzzy title matching."""

    def test_deduplicate_fuzzy_title_high_similarity(self) -> None:
        """Test papers with very similar titles are matched."""
        p1 = make_paper("p1", title="Machine Learning for NLP", year=2024)
        p2 = make_paper("p2", title="Machine Learning for NLP.", year=2024)
        
        dedup = Deduplicator(fuzzy_threshold=0.85)
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        assert len(deduped) == 1
        assert len(clusters) == 1
        assert clusters[0].match_type == "title_fuzzy"
        assert clusters[0].confidence >= 0.85

    def test_deduplicate_fuzzy_title_case_insensitive(self) -> None:
        """Test fuzzy matching is case-insensitive."""
        p1 = make_paper("p1", title="Deep Learning Survey", year=2024)
        p2 = make_paper("p2", title="DEEP LEARNING SURVEY", year=2024)
        
        dedup = Deduplicator(fuzzy_threshold=0.85)
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        assert len(deduped) == 1
        assert len(clusters) == 1

    def test_deduplicate_fuzzy_title_different_years_no_match(self) -> None:
        """Test fuzzy matching requires same year."""
        p1 = make_paper("p1", title="Machine Learning for NLP", year=2024)
        p2 = make_paper("p2", title="Machine Learning for NLP", year=2023)
        
        dedup = Deduplicator(fuzzy_threshold=0.85)
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        # Different years, should not match
        assert len(deduped) == 2
        assert len(clusters) == 0

    def test_deduplicate_fuzzy_title_below_threshold(self) -> None:
        """Test papers below fuzzy threshold are not matched."""
        p1 = make_paper("p1", title="Machine Learning", year=2024)
        p2 = make_paper("p2", title="Deep Learning", year=2024)
        
        dedup = Deduplicator(fuzzy_threshold=0.85)
        deduped, clusters = dedup.deduplicate([p1, p2])
        
        # Different titles, should not match
        assert len(deduped) == 2
        assert len(clusters) == 0

    def test_deduplicate_fuzzy_custom_threshold(self) -> None:
        """Test custom fuzzy threshold."""
        p1 = make_paper("p1", title="AI Survey", year=2024)
        p2 = make_paper("p2", title="AI Survey 2024", year=2024)
        
        # Lower threshold might match
        dedup_low = Deduplicator(fuzzy_threshold=0.75)
        deduped_low, clusters_low = dedup_low.deduplicate([p1, p2])
        
        # Higher threshold might not match
        dedup_high = Deduplicator(fuzzy_threshold=0.95)
        deduped_high, clusters_high = dedup_high.deduplicate([p1, p2])
        
        # At least one should behave differently
        assert len(deduped_low) != len(deduped_high) or len(clusters_low) != len(clusters_high)

    def test_deduplicate_fuzzy_only_unmatched_papers(self) -> None:
        """Test fuzzy matching only applies to papers not matched by DOI/arXiv."""
        papers = [
            make_paper("p1", doi="10.1234/a", title="Title A", year=2024),
            make_paper("p2", doi="10.1234/a", title="Title B", year=2024),  # Matches p1 by DOI
            make_paper("p3", title="Title C", year=2024),
            make_paper("p4", title="Title C", year=2024),  # Matches p3 by fuzzy title
        ]
        
        dedup = Deduplicator(fuzzy_threshold=0.85)
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 2
        assert len(clusters) == 2


class TestDeduplicatorMergeStrategy:
    """Tests for canonical selection and merging."""

    def test_merge_strategy_most_citations(self) -> None:
        """Test 'most_citations' merge strategy."""
        papers = [
            make_paper("p1", doi="10.1234/abc", citation_count=5),
            make_paper("p2", doi="10.1234/abc", citation_count=15),
            make_paper("p3", doi="10.1234/abc", citation_count=10),
        ]
        
        dedup = Deduplicator(merge_strategy="most_citations")
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 1
        assert deduped[0].paper_id == "p2"  # Most citations

    def test_merge_strategy_best_completeness(self) -> None:
        """Test 'best_completeness' merge strategy."""
        papers = [
            make_paper("p1", doi="10.1234/abc", abstract=None, citation_count=100),
            make_paper(
                "p2",
                doi="10.1234/abc",
                abstract="Full abstract",
                authors=[Author(name="Alice")],
                venue="Top Conference",
                is_open_access=True,
                open_access_pdf="https://example.com/pdf",
            ),
        ]
        
        dedup = Deduplicator(merge_strategy="best_completeness")
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 1
        # p2 should be canonical due to better completeness
        assert deduped[0].paper_id == "p2"

    def test_merge_paper_data_fields_of_study(self) -> None:
        """Test merging combines fields of study."""
        papers = [
            make_paper("p1", doi="10.1234/abc", fields_of_study=["CS", "AI"]),
            make_paper("p2", doi="10.1234/abc", fields_of_study=["AI", "ML"]),
        ]
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 1
        # Should have union of fields
        fields = set(deduped[0].fields_of_study)
        assert "CS" in fields
        assert "AI" in fields
        assert "ML" in fields

    def test_merge_paper_data_external_ids(self) -> None:
        """Test merging combines external IDs."""
        papers = [
            make_paper("p1", doi="10.1234/abc"),
            make_paper("p2", doi="10.1234/abc"),
        ]
        papers[0].external_ids = {"MAG": "123", "PubMed": "456"}
        papers[1].external_ids = {"MAG": "123", "Crossref": "789"}
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 1
        ext_ids = deduped[0].external_ids
        assert "MAG" in ext_ids
        assert "PubMed" in ext_ids
        assert "Crossref" in ext_ids

    def test_merge_paper_data_open_access(self) -> None:
        """Test merging preserves open access PDF if available."""
        papers = [
            make_paper("p1", doi="10.1234/abc", is_open_access=False),
            make_paper(
                "p2",
                doi="10.1234/abc",
                is_open_access=True,
                open_access_pdf="https://example.com/pdf",
            ),
        ]
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 1
        # Should preserve the OA PDF
        assert deduped[0].open_access_pdf == "https://example.com/pdf"

    def test_merge_paper_data_max_citations(self) -> None:
        """Test merging uses maximum citation counts."""
        papers = [
            make_paper("p1", doi="10.1234/abc", citation_count=10),
            make_paper("p2", doi="10.1234/abc", citation_count=25),
            make_paper("p3", doi="10.1234/abc", citation_count=15),
        ]
        papers[1].influential_citation_count = 5
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 1
        assert deduped[0].citation_count == 25
        assert deduped[0].influential_citation_count == 5


class TestDeduplicatorClusters:
    """Tests for deduplication cluster tracking."""

    def test_cluster_contains_duplicate_ids(self) -> None:
        """Test cluster tracks all duplicate IDs."""
        papers = [
            make_paper("p1", doi="10.1234/abc"),
            make_paper("p2", doi="10.1234/abc"),
            make_paper("p3", doi="10.1234/abc"),
        ]
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(clusters) == 1
        cluster = clusters[0]
        all_ids = {cluster.canonical_id} | set(cluster.duplicate_ids)
        assert all_ids == {"p1", "p2", "p3"}

    def test_get_canonical_id_mapping(self) -> None:
        """Test get_canonical_id returns correct mapping."""
        papers = [
            make_paper("p1", doi="10.1234/abc"),
            make_paper("p2", doi="10.1234/abc"),
            make_paper("p3", doi="10.5678/def"),  # Unique
        ]
        
        dedup = Deduplicator()
        dedup.deduplicate(papers)
        
        canonical_p1 = dedup.get_canonical_id("p1")
        canonical_p2 = dedup.get_canonical_id("p2")
        canonical_p3 = dedup.get_canonical_id("p3")
        
        # p1 and p2 should map to same canonical ID
        assert canonical_p1 == canonical_p2
        # p3 should map to itself
        assert canonical_p3 == "p3"

    def test_cluster_confidence_scores(self) -> None:
        """Test cluster confidence scores."""
        papers = [
            make_paper("p1", doi="10.1234/abc"),
            make_paper("p2", doi="10.1234/abc"),
            make_paper("p3", arxiv_id="1234.5678"),
            make_paper("p4", arxiv_id="1234.5678"),
            make_paper("p5", title="Test Title", year=2024),
            make_paper("p6", title="Test Title", year=2024),
        ]
        
        dedup = Deduplicator(fuzzy_threshold=0.85)
        deduped, clusters = dedup.deduplicate(papers)
        
        # DOI match should have confidence 1.0
        doi_cluster = [c for c in clusters if c.match_type == "doi"][0]
        assert doi_cluster.confidence == 1.0
        
        # arXiv match should have confidence 1.0
        arxiv_cluster = [c for c in clusters if c.match_type == "arxiv"][0]
        assert arxiv_cluster.confidence == 1.0
        
        # Fuzzy match should have confidence >= threshold
        if any(c.match_type == "title_fuzzy" for c in clusters):
            fuzzy_cluster = [c for c in clusters if c.match_type == "title_fuzzy"][0]
            assert fuzzy_cluster.confidence >= 0.85


class TestDeduplicatorEdgeCases:
    """Tests for edge cases."""

    def test_deduplicate_empty_list(self) -> None:
        """Test deduplication of empty paper list."""
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate([])
        
        assert len(deduped) == 0
        assert len(clusters) == 0

    def test_deduplicate_single_paper(self) -> None:
        """Test deduplication with single paper."""
        paper = make_paper("p1", doi="10.1234/abc")
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate([paper])
        
        assert len(deduped) == 1
        assert len(clusters) == 0
        assert deduped[0].paper_id == "p1"

    def test_deduplicate_no_duplicates(self) -> None:
        """Test deduplication with no duplicates."""
        papers = [
            make_paper("p1", doi="10.1234/a", title="First Paper About AI"),
            make_paper("p2", doi="10.1234/b", title="Second Paper About ML"),
            make_paper("p3", doi="10.1234/c", title="Third Paper About NLP"),
        ]
        
        dedup = Deduplicator()
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 3
        assert len(clusters) == 0

    def test_deduplicate_papers_without_year(self) -> None:
        """Test fuzzy matching skips papers without year."""
        papers = [
            make_paper("p1", title="Same Title", year=None),
            make_paper("p2", title="Same Title", year=None),
        ]
        
        dedup = Deduplicator(fuzzy_threshold=0.85)
        deduped, clusters = dedup.deduplicate(papers)
        
        # Without year, fuzzy matching should not occur
        assert len(deduped) == 2
        assert len(clusters) == 0

    def test_deduplicate_papers_with_empty_titles(self) -> None:
        """Test fuzzy matching handles empty/None titles gracefully."""
        papers = [
            make_paper("p1", title="", year=2024),
            make_paper("p2", title="Real Title", year=2024),
        ]
        
        dedup = Deduplicator(fuzzy_threshold=0.85)
        # Should not crash
        deduped, clusters = dedup.deduplicate(papers)
        
        assert len(deduped) == 2

