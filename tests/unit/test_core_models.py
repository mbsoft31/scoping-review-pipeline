"""Unit tests for core data models (Paper, Author, Source, etc.)."""

from datetime import date
import pytest
from pydantic import ValidationError

from srp.core.models import Author, Source, Paper, Reference, DeduplicationCluster


class TestAuthorModel:
    """Tests for Author model."""

    def test_author_minimal(self) -> None:
        """Test Author with only required field (name)."""
        author = Author(name="John Doe")
        assert author.name == "John Doe"
        assert author.author_id is None
        assert author.orcid is None
        assert author.affiliation is None

    def test_author_full(self) -> None:
        """Test Author with all fields."""
        author = Author(
            name="Jane Smith",
            author_id="A123456789",
            orcid="0000-0001-2345-6789",
            affiliation="MIT",
        )
        assert author.name == "Jane Smith"
        assert author.author_id == "A123456789"
        assert author.orcid == "0000-0001-2345-6789"
        assert author.affiliation == "MIT"


class TestSourceModel:
    """Tests for Source model."""

    def test_source_required_fields(self) -> None:
        """Test Source with required fields."""
        source = Source(
            database="openalex",
            query="machine learning",
            timestamp="2025-11-08T10:00:00Z",
        )
        assert source.database == "openalex"
        assert source.query == "machine learning"
        assert source.timestamp == "2025-11-08T10:00:00Z"
        assert source.page is None
        assert source.cursor is None

    def test_source_with_pagination(self) -> None:
        """Test Source with pagination info."""
        source = Source(
            database="semantic_scholar",
            query="NLP transformers",
            timestamp="2025-11-08T10:00:00Z",
            page=5,
            cursor="abc123",
        )
        assert source.page == 5
        assert source.cursor == "abc123"


class TestPaperModel:
    """Tests for Paper model."""

    def test_paper_minimal(self) -> None:
        """Test Paper with minimal required fields."""
        paper = Paper(
            paper_id="test:123",
            title="Sample Paper Title",
            source=Source(
                database="test",
                query="sample",
                timestamp="2025-11-08T10:00:00Z",
            ),
        )
        assert paper.paper_id == "test:123"
        assert paper.title == "Sample Paper Title"
        assert paper.doi is None
        assert paper.arxiv_id is None
        assert len(paper.authors) == 0
        assert paper.citation_count == 0
        assert paper.is_open_access is False

    def test_paper_full(self) -> None:
        """Test Paper with all fields populated."""
        authors = [
            Author(name="Alice", author_id="A1"),
            Author(name="Bob", author_id="A2"),
        ]
        paper = Paper(
            paper_id="openalex:W123",
            doi="10.1234/abc",
            arxiv_id="2401.12345",
            title="Deep Learning for NLP",
            abstract="This paper presents...",
            authors=authors,
            year=2024,
            publication_date=date(2024, 1, 15),
            venue="NeurIPS",
            publisher="ACM",
            fields_of_study=["Computer Science", "AI"],
            keywords=["NLP", "transformers"],
            citation_count=42,
            influential_citation_count=10,
            reference_count=50,
            is_open_access=True,
            open_access_pdf="https://arxiv.org/pdf/2401.12345.pdf",
            external_ids={"MAG": "123456", "PubMed": "789"},
            source=Source(
                database="openalex",
                query="NLP",
                timestamp="2025-11-08T10:00:00Z",
            ),
        )
        assert paper.paper_id == "openalex:W123"
        assert paper.doi == "10.1234/abc"
        assert paper.arxiv_id == "2401.12345"
        assert len(paper.authors) == 2
        assert paper.year == 2024
        assert paper.citation_count == 42
        assert paper.is_open_access is True

    def test_paper_doi_normalization(self) -> None:
        """Test DOI normalization in Paper model validator."""
        paper = Paper(
            paper_id="test:1",
            title="Test",
            doi="https://doi.org/10.1234/ABC",
            source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
        )
        # DOI should be normalized to lowercase without prefix
        assert paper.doi == "10.1234/abc"

    def test_paper_doi_normalization_variants(self) -> None:
        """Test various DOI prefix normalizations."""
        test_cases = [
            ("https://doi.org/10.1234/ABC", "10.1234/abc"),
            ("http://dx.doi.org/10.1234/ABC", "10.1234/abc"),
            ("DOI:10.1234/ABC", "10.1234/abc"),
            ("10.1234/ABC", "10.1234/abc"),
        ]
        for input_doi, expected_doi in test_cases:
            paper = Paper(
                paper_id="test:1",
                title="Test",
                doi=input_doi,
                source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
            )
            assert paper.doi == expected_doi

    def test_paper_arxiv_normalization(self) -> None:
        """Test arXiv ID normalization in Paper model validator."""
        paper = Paper(
            paper_id="test:1",
            title="Test",
            arxiv_id="arxiv:1234.5678",
            source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
        )
        assert paper.arxiv_id == "1234.5678"

    def test_paper_year_validation_valid(self) -> None:
        """Test year validation accepts valid years."""
        paper = Paper(
            paper_id="test:1",
            title="Test",
            year=2024,
            source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
        )
        assert paper.year == 2024

    def test_paper_year_validation_too_early(self) -> None:
        """Test year validation rejects years before 1900."""
        with pytest.raises(ValidationError):
            Paper(
                paper_id="test:1",
                title="Test",
                year=1899,
                source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
            )

    def test_paper_year_validation_too_late(self) -> None:
        """Test year validation rejects years after 2100."""
        with pytest.raises(ValidationError):
            Paper(
                paper_id="test:1",
                title="Test",
                year=2101,
                source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
            )

    def test_paper_citation_count_negative(self) -> None:
        """Test citation count cannot be negative."""
        with pytest.raises(ValidationError):
            Paper(
                paper_id="test:1",
                title="Test",
                citation_count=-1,
                source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
            )

    def test_paper_serialization(self) -> None:
        """Test Paper can be serialized to JSON."""
        paper = Paper(
            paper_id="test:1",
            title="Test Paper",
            doi="10.1234/test",
            year=2024,
            source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
        )
        json_data = paper.model_dump()
        assert json_data["paper_id"] == "test:1"
        assert json_data["title"] == "Test Paper"
        assert json_data["doi"] == "10.1234/test"

    def test_paper_deserialization(self) -> None:
        """Test Paper can be created from JSON."""
        data = {
            "paper_id": "test:1",
            "title": "Test Paper",
            "doi": "10.1234/test",
            "year": 2024,
            "source": {
                "database": "test",
                "query": "test",
                "timestamp": "2025-11-08T10:00:00Z",
            },
        }
        paper = Paper(**data)
        assert paper.paper_id == "test:1"
        assert paper.title == "Test Paper"

    def test_paper_model_copy_deep(self) -> None:
        """Test deep copy doesn't share references."""
        original = Paper(
            paper_id="test:1",
            title="Original",
            authors=[Author(name="Alice")],
            fields_of_study=["CS"],
            source=Source(database="test", query="test", timestamp="2025-11-08T10:00:00Z"),
        )
        copy = original.model_copy(deep=True)

        # Modify the copy
        copy.authors.append(Author(name="Bob"))
        copy.fields_of_study.append("AI")

        # Original should be unchanged
        assert len(original.authors) == 1
        assert len(original.fields_of_study) == 1


class TestReferenceModel:
    """Tests for Reference model."""

    def test_reference_minimal(self) -> None:
        """Test Reference with minimal fields."""
        ref = Reference(
            citing_paper_id="paper:1",
            source="openalex",
        )
        assert ref.citing_paper_id == "paper:1"
        assert ref.source == "openalex"
        assert ref.cited_doi is None
        assert ref.cited_paper_id is None

    def test_reference_full(self) -> None:
        """Test Reference with all fields."""
        ref = Reference(
            citing_paper_id="paper:1",
            cited_doi="10.1234/cited",
            cited_paper_id="paper:2",
            cited_title="Cited Paper",
            source="semantic_scholar",
            context="This work builds on...",
        )
        assert ref.cited_doi == "10.1234/cited"
        assert ref.cited_paper_id == "paper:2"
        assert ref.context == "This work builds on..."


class TestDeduplicationClusterModel:
    """Tests for DeduplicationCluster model."""

    def test_cluster_valid(self) -> None:
        """Test valid DeduplicationCluster."""
        cluster = DeduplicationCluster(
            canonical_id="paper:1",
            duplicate_ids=["paper:2", "paper:3"],
            match_type="doi",
            confidence=1.0,
        )
        assert cluster.canonical_id == "paper:1"
        assert len(cluster.duplicate_ids) == 2
        assert cluster.match_type == "doi"
        assert cluster.confidence == 1.0

    def test_cluster_confidence_validation_low(self) -> None:
        """Test confidence must be >= 0.0."""
        with pytest.raises(ValidationError):
            DeduplicationCluster(
                canonical_id="paper:1",
                duplicate_ids=["paper:2"],
                match_type="doi",
                confidence=-0.1,
            )

    def test_cluster_confidence_validation_high(self) -> None:
        """Test confidence must be <= 1.0."""
        with pytest.raises(ValidationError):
            DeduplicationCluster(
                canonical_id="paper:1",
                duplicate_ids=["paper:2"],
                match_type="doi",
                confidence=1.1,
            )

    def test_cluster_fuzzy_match(self) -> None:
        """Test cluster with fuzzy matching."""
        cluster = DeduplicationCluster(
            canonical_id="paper:1",
            duplicate_ids=["paper:2"],
            match_type="title_fuzzy",
            confidence=0.87,
        )
        assert cluster.match_type == "title_fuzzy"
        assert 0.85 <= cluster.confidence < 0.9
"""Unit tests for systematic review pipeline modules."""

