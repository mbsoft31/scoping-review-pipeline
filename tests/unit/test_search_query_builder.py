"""Unit tests for QueryBuilder systematic query generation."""

import pytest
from pathlib import Path

from srp.search.query_builder import QueryBuilder


class TestQueryBuilderCorePairs:
    """Tests for core pair query generation."""

    def test_generate_core_pairs_basic(self) -> None:
        """Test basic pair generation from terms."""
        builder = QueryBuilder()
        terms = ["machine learning", "NLP", "transformers"]

        pairs = builder.generate_core_pairs(terms)

        # Should generate C(3,2) = 3 pairs
        assert len(pairs) == 3
        assert "machine learning NLP" in pairs
        assert "machine learning transformers" in pairs
        assert "NLP transformers" in pairs

    def test_generate_core_pairs_two_terms(self) -> None:
        """Test pair generation with exactly two terms."""
        builder = QueryBuilder()
        terms = ["deep learning", "neural networks"]

        pairs = builder.generate_core_pairs(terms)

        assert len(pairs) == 1
        assert pairs[0] == "deep learning neural networks"

    def test_generate_core_pairs_single_term(self) -> None:
        """Test pair generation with single term."""
        builder = QueryBuilder()
        terms = ["AI"]

        pairs = builder.generate_core_pairs(terms)

        # No pairs possible with 1 term
        assert len(pairs) == 0

    def test_generate_core_pairs_many_terms(self) -> None:
        """Test pair generation with many terms."""
        builder = QueryBuilder()
        terms = ["A", "B", "C", "D", "E"]

        pairs = builder.generate_core_pairs(terms)

        # C(5,2) = 10 pairs
        assert len(pairs) == 10


class TestQueryBuilderAugmentation:
    """Tests for query augmentation."""

    def test_generate_augmented_queries_basic(self) -> None:
        """Test basic query augmentation."""
        builder = QueryBuilder()
        core_queries = ["machine learning NLP"]
        augmentation_terms = ["deep learning", "transformers"]

        augmented = builder.generate_augmented_queries(
            core_queries, augmentation_terms, max_augmentations=2
        )

        # Should include original + augmented versions
        assert "machine learning NLP" in augmented
        assert "machine learning NLP deep learning transformers" in augmented

    def test_generate_augmented_queries_single_augmentation(self) -> None:
        """Test augmentation with max_augmentations=1."""
        builder = QueryBuilder()
        core_queries = ["AI research"]
        augmentation_terms = ["neural networks", "optimization"]

        augmented = builder.generate_augmented_queries(
            core_queries, augmentation_terms, max_augmentations=1
        )

        # Should include: original, +neural, +optimization
        assert len(augmented) >= 3
        assert "AI research" in augmented

    def test_generate_augmented_queries_empty_augmentation(self) -> None:
        """Test augmentation with no augmentation terms."""
        builder = QueryBuilder()
        core_queries = ["AI research"]
        augmentation_terms = []

        augmented = builder.generate_augmented_queries(
            core_queries, augmentation_terms, max_augmentations=2
        )

        # Should just return original queries
        assert augmented == ["AI research"]

    def test_generate_augmented_queries_multiple_core(self) -> None:
        """Test augmentation with multiple core queries."""
        builder = QueryBuilder()
        core_queries = ["AI ML", "NLP transformers"]
        augmentation_terms = ["deep learning"]

        augmented = builder.generate_augmented_queries(
            core_queries, augmentation_terms, max_augmentations=1
        )

        # Should augment each core query
        assert "AI ML" in augmented
        assert "NLP transformers" in augmented
        assert "AI ML deep learning" in augmented
        assert "NLP transformers deep learning" in augmented


class TestQueryBuilderSourceOptimization:
    """Tests for source-specific optimization."""

    def test_optimize_for_semantic_scholar_long_query(self) -> None:
        """Test query optimization for Semantic Scholar (truncates long queries)."""
        builder = QueryBuilder()
        query = "machine learning deep learning neural networks transformers attention"

        optimized = builder.optimize_for_source(query, "semantic_scholar")

        # Should truncate to first 4 terms
        terms = optimized.split()
        assert len(terms) == 4

    def test_optimize_for_semantic_scholar_short_query(self) -> None:
        """Test query optimization for S2 with short query (no truncation)."""
        builder = QueryBuilder()
        query = "AI ML NLP"

        optimized = builder.optimize_for_source(query, "semantic_scholar")

        # Should remain unchanged
        assert optimized == "AI ML NLP"

    def test_optimize_for_other_sources(self) -> None:
        """Test optimization for non-S2 sources (no change)."""
        builder = QueryBuilder()
        query = "very long query with many terms that should not be truncated"

        for source in ["openalex", "crossref", "arxiv"]:
            optimized = builder.optimize_for_source(query, source)
            assert optimized == query


class TestQueryBuilderSystematicGeneration:
    """Tests for systematic query generation."""

    def test_generate_systematic_queries_basic(self) -> None:
        """Test systematic query generation."""
        builder = QueryBuilder()
        core_terms = ["machine learning", "NLP"]

        queries = builder.generate_systematic_queries(
            core_terms, include_augmented=False
        )

        # Should generate C(2,2) = 1 pair
        assert len(queries) == 1
        assert "machine learning NLP" in queries

    def test_generate_systematic_queries_with_methods(self) -> None:
        """Test systematic queries with method augmentation."""
        builder = QueryBuilder()
        core_terms = ["AI", "ML"]
        method_terms = ["deep learning"]

        queries = builder.generate_systematic_queries(
            core_terms, method_terms=method_terms, include_augmented=True
        )

        # Should include base + method-augmented
        assert len(queries) > 1
        assert "AI ML" in queries

    def test_generate_systematic_queries_with_context(self) -> None:
        """Test systematic queries with context augmentation."""
        builder = QueryBuilder()
        core_terms = ["AI", "ML"]
        context_terms = ["healthcare"]

        queries = builder.generate_systematic_queries(
            core_terms, context_terms=context_terms, include_augmented=True
        )

        # Should include base + context-augmented
        assert len(queries) > 1
        assert "AI ML" in queries

    def test_generate_systematic_queries_no_duplicates(self) -> None:
        """Test systematic queries have no duplicates."""
        builder = QueryBuilder()
        core_terms = ["A", "B", "C"]
        method_terms = ["D"]
        context_terms = ["D"]  # Intentionally same as method

        queries = builder.generate_systematic_queries(
            core_terms,
            method_terms=method_terms,
            context_terms=context_terms,
            include_augmented=True,
        )

        # Should deduplicate
        assert len(queries) == len(set(queries))

    def test_generate_systematic_queries_sorted(self) -> None:
        """Test systematic queries are sorted."""
        builder = QueryBuilder()
        core_terms = ["Z", "A", "M"]

        queries = builder.generate_systematic_queries(
            core_terms, include_augmented=False
        )

        # Should be sorted
        assert queries == sorted(queries)


class TestQueryBuilderSaveQueries:
    """Tests for query persistence."""

    def test_save_queries_creates_file(self, tmp_path: Path) -> None:
        """Test saving queries creates a file."""
        builder = QueryBuilder()
        queries = ["query1", "query2", "query3"]
        output_path = tmp_path / "queries.md"

        builder.save_queries(queries, output_path)

        assert output_path.exists()

    def test_save_queries_content(self, tmp_path: Path) -> None:
        """Test saved queries file has correct content."""
        builder = QueryBuilder()
        queries = ["machine learning", "deep learning"]
        output_path = tmp_path / "queries.md"

        builder.save_queries(queries, output_path)

        content = output_path.read_text()
        assert "Total queries: 2" in content
        assert "`machine learning`" in content
        assert "`deep learning`" in content

    def test_save_queries_empty_list(self, tmp_path: Path) -> None:
        """Test saving empty query list."""
        builder = QueryBuilder()
        queries = []
        output_path = tmp_path / "queries.md"

        builder.save_queries(queries, output_path)

        assert output_path.exists()
        content = output_path.read_text()
        assert "Total queries: 0" in content


class TestQueryBuilderConfiguration:
    """Tests for configuration loading."""

    def test_query_builder_default_config(self) -> None:
        """Test QueryBuilder with default configuration."""
        builder = QueryBuilder()

        assert builder.config is not None
        assert "boolean_operators" in builder.config

    def test_query_builder_custom_config(self, tmp_path: Path) -> None:
        """Test QueryBuilder with custom configuration file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
core_terms:
  - AI
  - ML
method_terms:
  - deep learning
max_terms_per_query: 3
"""
        )

        builder = QueryBuilder(config_path)

        assert builder.config["core_terms"] == ["AI", "ML"]
        assert builder.config["method_terms"] == ["deep learning"]
        assert builder.config["max_terms_per_query"] == 3

    def test_query_builder_nonexistent_config(self) -> None:
        """Test QueryBuilder with nonexistent config file falls back to defaults."""
        builder = QueryBuilder(Path("/nonexistent/config.yaml"))

        # Should use default config
        assert builder.config is not None
        assert "boolean_operators" in builder.config

