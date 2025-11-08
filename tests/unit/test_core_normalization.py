"""Unit tests for text and metadata normalization utilities."""

from datetime import date, datetime
import pytest

from srp.core.normalization import (
    normalize_title,
    parse_date,
    extract_year,
    clean_abstract,
)


class TestNormalizeTitle:
    """Tests for title normalization."""

    def test_normalize_title_basic(self) -> None:
        """Test basic title normalization."""
        result = normalize_title("Machine Learning for NLP")
        assert result == "machine learning for nlp"

    def test_normalize_title_lowercase(self) -> None:
        """Test title is converted to lowercase."""
        assert normalize_title("UPPERCASE TITLE") == "uppercase title"
        assert normalize_title("MiXeD CaSe") == "mixed case"

    def test_normalize_title_punctuation_removal(self) -> None:
        """Test punctuation is removed."""
        assert normalize_title("Title: A Survey!") == "title a survey"
        assert normalize_title("What is AI?") == "what is ai"
        assert normalize_title("Machine-Learning") == "machinelearning"

    def test_normalize_title_whitespace_normalization(self) -> None:
        """Test multiple spaces become single space."""
        assert normalize_title("Title  with   extra    spaces") == "title with extra spaces"
        assert normalize_title("Title\twith\ttabs") == "title with tabs"
        assert normalize_title("Title\nwith\nnewlines") == "title with newlines"

    def test_normalize_title_leading_trailing_whitespace(self) -> None:
        """Test leading/trailing whitespace is removed."""
        assert normalize_title("  Title  ") == "title"
        assert normalize_title("\t\nTitle\n\t") == "title"

    def test_normalize_title_special_characters(self) -> None:
        """Test special characters are removed."""
        assert normalize_title("AI & ML: The Future?") == "ai ml the future"
        assert normalize_title("(Deep Learning) [Review]") == "deep learning review"

    def test_normalize_title_empty(self) -> None:
        """Test empty string returns empty string."""
        assert normalize_title("") == ""
        assert normalize_title("   ") == ""

    def test_normalize_title_numbers_preserved(self) -> None:
        """Test numbers are preserved."""
        assert normalize_title("GPT-3: A Survey") == "gpt3 a survey"
        assert normalize_title("The Year 2024") == "the year 2024"

    def test_normalize_title_unicode(self) -> None:
        """Test unicode characters handling."""
        # Depending on implementation, unicode may be kept or removed
        result = normalize_title("Café: A Study")
        assert "caf" in result.lower() or "cafe" in result.lower()


class TestParseDate:
    """Tests for date parsing."""

    def test_parse_date_iso_format(self) -> None:
        """Test ISO format YYYY-MM-DD."""
        result = parse_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_parse_date_slash_format(self) -> None:
        """Test slash format YYYY/MM/DD."""
        result = parse_date("2024/01/15")
        assert result == date(2024, 1, 15)

    def test_parse_date_year_month_only(self) -> None:
        """Test YYYY-MM format (day defaults to 1)."""
        result = parse_date("2024-01")
        assert result == date(2024, 1, 1)

    def test_parse_date_year_only(self) -> None:
        """Test YYYY format (month and day default to 1)."""
        result = parse_date("2024")
        assert result == date(2024, 1, 1)

    def test_parse_date_dmy_dash_format(self) -> None:
        """Test DD-MM-YYYY format."""
        result = parse_date("15-01-2024")
        assert result == date(2024, 1, 15)

    def test_parse_date_dmy_slash_format(self) -> None:
        """Test DD/MM/YYYY format."""
        result = parse_date("15/01/2024")
        assert result == date(2024, 1, 15)

    def test_parse_date_none(self) -> None:
        """Test None input returns None."""
        assert parse_date(None) is None

    def test_parse_date_empty_string(self) -> None:
        """Test empty string returns None."""
        assert parse_date("") is None

    def test_parse_date_invalid_format(self) -> None:
        """Test invalid date format returns None."""
        assert parse_date("not-a-date") is None
        assert parse_date("13-13-2024") is None  # Invalid month
        assert parse_date("2024-02-30") is None  # Invalid day

    def test_parse_date_partial_match(self) -> None:
        """Test date parsing with extra characters."""
        # Should parse the date part and ignore the rest
        result = parse_date("2024-01-15T10:30:00Z")
        assert result == date(2024, 1, 15)

    def test_parse_date_edge_cases(self) -> None:
        """Test edge case dates."""
        assert parse_date("2024-12-31") == date(2024, 12, 31)
        assert parse_date("2000-01-01") == date(2000, 1, 1)


class TestExtractYear:
    """Tests for year extraction from date."""

    def test_extract_year_valid_date(self) -> None:
        """Test extracting year from valid date."""
        d = date(2024, 6, 15)
        assert extract_year(d) == 2024

    def test_extract_year_different_years(self) -> None:
        """Test different years."""
        assert extract_year(date(2020, 1, 1)) == 2020
        assert extract_year(date(1999, 12, 31)) == 1999
        assert extract_year(date(2025, 7, 4)) == 2025

    def test_extract_year_none(self) -> None:
        """Test None input returns None."""
        assert extract_year(None) is None

    def test_extract_year_leap_year(self) -> None:
        """Test year extraction on leap year date."""
        d = date(2024, 2, 29)
        assert extract_year(d) == 2024


class TestCleanAbstract:
    """Tests for abstract cleaning."""

    def test_clean_abstract_basic(self) -> None:
        """Test basic abstract cleaning."""
        abstract = "This is a sample abstract."
        result = clean_abstract(abstract)
        assert result == "This is a sample abstract."

    def test_clean_abstract_whitespace_normalization(self) -> None:
        """Test multiple spaces/newlines become single space."""
        abstract = "This  is   a    sample\n\nabstract  with   extra   whitespace."
        result = clean_abstract(abstract)
        assert "  " not in result
        assert "\n" not in result
        assert result == "This is a sample abstract with extra whitespace."

    def test_clean_abstract_truncation(self) -> None:
        """Test abstract is truncated at max_length."""
        abstract = "A" * 6000
        result = clean_abstract(abstract, max_length=5000)
        assert len(result) <= 5003  # 5000 + "..."
        assert result.endswith("...")

    def test_clean_abstract_no_truncation_needed(self) -> None:
        """Test abstract shorter than max_length is not truncated."""
        abstract = "Short abstract."
        result = clean_abstract(abstract, max_length=5000)
        assert result == "Short abstract."
        assert not result.endswith("...")

    def test_clean_abstract_exact_max_length(self) -> None:
        """Test abstract exactly at max_length."""
        abstract = "A" * 5000
        result = clean_abstract(abstract, max_length=5000)
        # Should not be truncated if exactly at limit
        assert len(result) == 5000

    def test_clean_abstract_none(self) -> None:
        """Test None input returns None."""
        assert clean_abstract(None) is None

    def test_clean_abstract_empty_string(self) -> None:
        """Test empty string returns None."""
        assert clean_abstract("") is None
        assert clean_abstract("   ") is None

    def test_clean_abstract_custom_max_length(self) -> None:
        """Test custom max_length parameter."""
        abstract = "A" * 150
        result = clean_abstract(abstract, max_length=100)
        assert len(result) <= 103  # 100 + "..."
        assert result.endswith("...")

    def test_clean_abstract_tabs_and_newlines(self) -> None:
        """Test tabs and newlines are normalized."""
        abstract = "Abstract\twith\ttabs\nand\nnewlines."
        result = clean_abstract(abstract)
        assert "\t" not in result
        assert "\n" not in result
        assert result == "Abstract with tabs and newlines."

    def test_clean_abstract_leading_trailing_whitespace(self) -> None:
        """Test leading and trailing whitespace is removed."""
        abstract = "   Abstract with spaces.   "
        result = clean_abstract(abstract)
        assert result == "Abstract with spaces."

