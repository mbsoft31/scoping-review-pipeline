"""Tests for core utilities such as ID normalization."""

from srp.core.ids import normalize_doi, normalize_arxiv_id


def test_normalize_doi() -> None:
    # Standard DOI with HTTPS prefix
    assert normalize_doi("https://doi.org/10.1234/ABC") == "10.1234/abc"
    # DOI with DX prefix and uppercase
    assert normalize_doi("http://dx.doi.org/10.1016/J.PHYSREP.2020.01.01") == "10.1016/j.physrep.2020.01.01"
    # DOI with doi: prefix and trailing spaces
    assert normalize_doi("DOI:10.5555/1234567 ") == "10.5555/1234567"
    # None stays None
    assert normalize_doi(None) is None


def test_normalize_arxiv_id() -> None:
    # Canonical arXiv with version
    assert normalize_arxiv_id("arxiv:1234.5678v2") == "1234.5678"
    # Without prefix but with version
    assert normalize_arxiv_id("1234.5678v3") == "1234.5678"
    # No version remains the same
    assert normalize_arxiv_id("1234.5678") == "1234.5678"
    # None stays None
    assert normalize_arxiv_id(None) is None