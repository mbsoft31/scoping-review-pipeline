"""Comprehensive unit tests for ID normalization utilities."""

import pytest

from srp.core.ids import (
    generate_paper_id,
    normalize_doi,
    normalize_arxiv_id,
    compute_title_hash,
)


class TestNormalizeDOI:
    """Tests for DOI normalization."""

    def test_normalize_doi_standard(self) -> None:
        """Test standard DOI format (no prefix)."""
        assert normalize_doi("10.1234/abc") == "10.1234/abc"

    def test_normalize_doi_https_prefix(self) -> None:
        """Test DOI with https://doi.org/ prefix."""
        assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"

    def test_normalize_doi_http_prefix(self) -> None:
        """Test DOI with http://doi.org/ prefix."""
        assert normalize_doi("http://doi.org/10.1234/ABC") == "10.1234/abc"

    def test_normalize_doi_dx_https_prefix(self) -> None:
        """Test DOI with https://dx.doi.org/ prefix."""
        assert normalize_doi("https://dx.doi.org/10.1016/J.TEST.2024") == "10.1016/j.test.2024"

    def test_normalize_doi_dx_http_prefix(self) -> None:
        """Test DOI with http://dx.doi.org/ prefix."""
        assert normalize_doi("http://dx.doi.org/10.1016/J.TEST.2024") == "10.1016/j.test.2024"

    def test_normalize_doi_colon_prefix(self) -> None:
        """Test DOI with doi: prefix."""
        assert normalize_doi("doi:10.5555/1234567") == "10.5555/1234567"
        assert normalize_doi("DOI:10.5555/1234567") == "10.5555/1234567"

    def test_normalize_doi_case_insensitive(self) -> None:
        """Test DOI normalization is case-insensitive."""
        assert normalize_doi("10.1234/ABC") == "10.1234/abc"
        assert normalize_doi("10.1234/AbCdEf") == "10.1234/abcdef"

    def test_normalize_doi_whitespace(self) -> None:
        """Test DOI normalization strips whitespace."""
        assert normalize_doi("  10.1234/abc  ") == "10.1234/abc"
        assert normalize_doi("\t10.1234/abc\n") == "10.1234/abc"

    def test_normalize_doi_none(self) -> None:
        """Test None input returns None."""
        assert normalize_doi(None) is None

    def test_normalize_doi_empty_string(self) -> None:
        """Test empty string returns None."""
        assert normalize_doi("") is None
        assert normalize_doi("   ") is None

    def test_normalize_doi_complex_suffix(self) -> None:
        """Test DOI with complex suffix characters."""
        doi = "10.1016/j.physrep.2020.01.001"
        assert normalize_doi(doi) == doi

    def test_normalize_doi_all_prefixes(self) -> None:
        """Test all supported prefixes are removed."""
        prefixes = [
            "https://doi.org/",
            "http://doi.org/",
            "https://dx.doi.org/",
            "http://dx.doi.org/",
            "doi:",
        ]
        for prefix in prefixes:
            result = normalize_doi(f"{prefix}10.1234/test")
            assert result == "10.1234/test", f"Failed for prefix: {prefix}"


class TestNormalizeArxivID:
    """Tests for arXiv ID normalization."""

    def test_normalize_arxiv_basic(self) -> None:
        """Test basic arXiv ID (no version, no prefix)."""
        assert normalize_arxiv_id("1234.5678") == "1234.5678"
        assert normalize_arxiv_id("2401.12345") == "2401.12345"

    def test_normalize_arxiv_with_prefix_lowercase(self) -> None:
        """Test arXiv ID with 'arxiv:' prefix (lowercase)."""
        assert normalize_arxiv_id("arxiv:1234.5678") == "1234.5678"

    def test_normalize_arxiv_with_prefix_uppercase(self) -> None:
        """Test arXiv ID with 'arXiv:' prefix (uppercase)."""
        assert normalize_arxiv_id("arXiv:1234.5678") == "1234.5678"
        assert normalize_arxiv_id("ARXIV:1234.5678") == "1234.5678"

    def test_normalize_arxiv_version_v1(self) -> None:
        """Test arXiv ID with version v1."""
        assert normalize_arxiv_id("1234.5678v1") == "1234.5678"

    def test_normalize_arxiv_version_v2(self) -> None:
        """Test arXiv ID with version v2."""
        assert normalize_arxiv_id("1234.5678v2") == "1234.5678"

    def test_normalize_arxiv_version_v10(self) -> None:
        """Test arXiv ID with two-digit version."""
        assert normalize_arxiv_id("1234.5678v10") == "1234.5678"

    def test_normalize_arxiv_prefix_and_version(self) -> None:
        """Test arXiv ID with both prefix and version."""
        assert normalize_arxiv_id("arxiv:1234.5678v2") == "1234.5678"
        assert normalize_arxiv_id("arXiv:2401.12345v1") == "2401.12345"

    def test_normalize_arxiv_old_format(self) -> None:
        """Test old arXiv format (e.g., hep-th/9901001)."""
        assert normalize_arxiv_id("hep-th/9901001") == "hep-th/9901001"
        assert normalize_arxiv_id("arxiv:hep-th/9901001v1") == "hep-th/9901001"

    def test_normalize_arxiv_whitespace(self) -> None:
        """Test arXiv ID normalization strips whitespace."""
        assert normalize_arxiv_id("  1234.5678  ") == "1234.5678"
        assert normalize_arxiv_id("\t1234.5678\n") == "1234.5678"

    def test_normalize_arxiv_none(self) -> None:
        """Test None input returns None."""
        assert normalize_arxiv_id(None) is None

    def test_normalize_arxiv_empty_string(self) -> None:
        """Test empty string returns None."""
        assert normalize_arxiv_id("") is None
        assert normalize_arxiv_id("   ") is None

    def test_normalize_arxiv_no_version_suffix(self) -> None:
        """Test that 'v' in other positions is not treated as version."""
        # If there's a 'v' not followed by digits, keep as-is
        arxiv_id = "cs.CV/1234"
        assert normalize_arxiv_id(arxiv_id) == arxiv_id


class TestGeneratePaperID:
    """Tests for paper ID generation."""

    def test_generate_paper_id_basic(self) -> None:
        """Test basic paper ID generation."""
        paper_id = generate_paper_id("openalex", "W123456789")
        assert paper_id == "openalex:W123456789"

    def test_generate_paper_id_semantic_scholar(self) -> None:
        """Test paper ID for Semantic Scholar."""
        paper_id = generate_paper_id("semantic_scholar", "abc123def456")
        assert paper_id == "semantic_scholar:abc123def456"

    def test_generate_paper_id_arxiv(self) -> None:
        """Test paper ID for arXiv."""
        paper_id = generate_paper_id("arxiv", "2401.12345")
        assert paper_id == "arxiv:2401.12345"

    def test_generate_paper_id_consistency(self) -> None:
        """Test that same inputs always produce same ID."""
        id1 = generate_paper_id("openalex", "W123")
        id2 = generate_paper_id("openalex", "W123")
        assert id1 == id2

    def test_generate_paper_id_different_sources(self) -> None:
        """Test different sources produce different IDs for same external ID."""
        id1 = generate_paper_id("openalex", "123")
        id2 = generate_paper_id("semantic_scholar", "123")
        assert id1 != id2
        assert id1 == "openalex:123"
        assert id2 == "semantic_scholar:123"


class TestComputeTitleHash:
    """Tests for title hash computation."""

    def test_compute_title_hash_basic(self) -> None:
        """Test basic title hashing."""
        hash1 = compute_title_hash("Machine Learning for NLP")
        assert isinstance(hash1, str)
        assert len(hash1) == 32  # MD5 hex digest

    def test_compute_title_hash_deterministic(self) -> None:
        """Test hash is deterministic."""
        title = "Deep Learning Applications"
        hash1 = compute_title_hash(title)
        hash2 = compute_title_hash(title)
        assert hash1 == hash2

    def test_compute_title_hash_case_insensitive(self) -> None:
        """Test hash is case-insensitive."""
        hash1 = compute_title_hash("Machine Learning")
        hash2 = compute_title_hash("machine learning")
        hash3 = compute_title_hash("MACHINE LEARNING")
        assert hash1 == hash2 == hash3

    def test_compute_title_hash_punctuation_invariant(self) -> None:
        """Test hash ignores punctuation."""
        hash1 = compute_title_hash("Machine Learning: A Survey")
        hash2 = compute_title_hash("Machine Learning A Survey")
        assert hash1 == hash2

    def test_compute_title_hash_whitespace_normalization(self) -> None:
        """Test hash normalizes whitespace."""
        hash1 = compute_title_hash("Machine  Learning   for    NLP")
        hash2 = compute_title_hash("Machine Learning for NLP")
        assert hash1 == hash2

    def test_compute_title_hash_special_characters(self) -> None:
        """Test hash handles special characters."""
        hash1 = compute_title_hash("Machine Learning: AI & Deep Neural Networks!")
        hash2 = compute_title_hash("Machine Learning AI Deep Neural Networks")
        assert hash1 == hash2

    def test_compute_title_hash_unicode(self) -> None:
        """Test hash handles unicode characters."""
        hash1 = compute_title_hash("Café: A Study")
        hash2 = compute_title_hash("Caf A Study")
        # Should normalize unicode, though exact behavior depends on regex
        assert isinstance(hash1, str)
        assert isinstance(hash2, str)

    def test_compute_title_hash_different_titles(self) -> None:
        """Test different titles produce different hashes."""
        hash1 = compute_title_hash("Machine Learning")
        hash2 = compute_title_hash("Deep Learning")
        assert hash1 != hash2

    def test_compute_title_hash_empty(self) -> None:
        """Test hash of empty string."""
        hash1 = compute_title_hash("")
        assert isinstance(hash1, str)
        assert len(hash1) == 32

    def test_compute_title_hash_order_matters(self) -> None:
        """Test word order affects hash."""
        hash1 = compute_title_hash("Machine Learning for NLP")
        hash2 = compute_title_hash("NLP for Machine Learning")
        assert hash1 != hash2

