"""Integration tests for I/O operations and data persistence.

These tests verify that data can be properly saved, loaded, and validated
across different formats and that caching mechanisms work correctly.
"""

import asyncio
from datetime import date, datetime
from pathlib import Path
import tempfile
import shutil

import pandas as pd
import pytest

from srp.core.models import Paper, Author, Source, Reference
from srp.io.cache import SearchCache
from srp.io.paths import get_cache_path
from srp.io.bibtex import BibTeXExporter
from srp.io.validation import validate_phase_output
from srp.search.orchestrator import SearchOrchestrator


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for I/O tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_papers():
    """Create sample papers for I/O testing."""
    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="io test", timestamp=timestamp)

    return [
        Paper(
            paper_id=f"io:test{i}",
            doi=f"10.1234/io{i}",
            title=f"I/O Test Paper {i}",
            authors=[Author(name=f"Author {i}"), Author(name=f"CoAuthor {i}")],
            year=2023,
            venue="Test Journal",
            abstract=f"Abstract for paper {i}.",
            citation_count=i * 10,
            external_ids={"doi": f"10.1234/io{i}", "openalex": f"W{i}"},
            source=source,
        )
        for i in range(5)
    ]


@pytest.mark.integration
def test_parquet_roundtrip(sample_papers, temp_workspace):
    """Test saving and loading papers to/from Parquet format."""
    output_file = temp_workspace / "papers.parquet"

    # Save to Parquet
    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in sample_papers])
    df.to_parquet(output_file, index=False)

    assert output_file.exists()
    assert output_file.stat().st_size > 0

    # Load from Parquet
    loaded_df = pd.read_parquet(output_file)

    assert len(loaded_df) == len(sample_papers)
    assert "paper_id" in loaded_df.columns
    assert "title" in loaded_df.columns
    assert "authors" in loaded_df.columns
    assert "year" in loaded_df.columns

    # Verify data integrity
    for i, paper in enumerate(sample_papers):
        row = loaded_df[loaded_df["paper_id"] == paper.paper_id].iloc[0]
        assert row["title"] == paper.title
        assert row["doi"] == paper.doi
        assert row["year"] == paper.year


@pytest.mark.integration
def test_csv_export(sample_papers, temp_workspace):
    """Test exporting papers to CSV format."""
    output_file = temp_workspace / "papers.csv"

    # Convert to DataFrame and save
    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in sample_papers])
    df.to_csv(output_file, index=False)

    assert output_file.exists()

    # Load and verify
    loaded_df = pd.read_csv(output_file)

    assert len(loaded_df) == len(sample_papers)
    assert "paper_id" in loaded_df.columns
    assert "title" in loaded_df.columns


@pytest.mark.integration
def test_bibtex_export_detailed(sample_papers, temp_workspace):
    """Test detailed BibTeX export functionality."""
    output_file = temp_workspace / "papers.bib"

    exporter = BibTeXExporter()
    exporter.export(sample_papers, output_file)

    assert output_file.exists()

    # Read and verify content (use UTF-8 encoding)
    content = output_file.read_text(encoding='utf-8')

    # Should have entries for each paper
    assert content.count("@") >= len(sample_papers)

    # Verify specific fields are present
    for paper in sample_papers:
        assert paper.title in content or paper.title.lower() in content.lower()
        if paper.doi:
            assert paper.doi in content

    # Check BibTeX structure
    assert "@article" in content.lower() or "@inproceedings" in content.lower()
    assert "title" in content.lower()
    assert "author" in content.lower()
    assert "year" in content


@pytest.mark.integration
def test_cache_functionality(temp_workspace):
    """Test SearchCache save/load functionality."""
    cache_path = temp_workspace / "cache"
    cache = SearchCache(cache_path)

    # Register a query
    query_id = cache.register_query(
        source="test_source",
        query="test query string",
        start_date="2023-01-01",
        end_date="2023-12-31",
    )

    assert query_id is not None

    # Create and cache papers
    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="test", timestamp=timestamp)

    papers = [
        Paper(
            paper_id=f"cache:paper{i}",
            title=f"Cached Paper {i}",
            authors=[Author(name=f"Author {i}")],
            year=2023,
            citation_count=i,
            external_ids={"source": source.database},
            source=source,
        )
        for i in range(3)
    ]

    for paper in papers:
        cache.cache_paper(query_id, paper)

    # Retrieve cached papers
    cached_papers = cache.get_cached_papers(query_id)

    assert len(cached_papers) == len(papers)

    for original, cached in zip(papers, cached_papers):
        assert original.paper_id == cached.paper_id
        assert original.title == cached.title

    # Check progress
    progress = cache.get_query_progress(query_id)
    assert progress is not None
    assert progress["source"] == "test_source"
    assert not progress["completed"]

    # Mark as completed
    cache.mark_completed(query_id)

    progress = cache.get_query_progress(query_id)
    assert progress["completed"]

    cache.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_resume_integration(temp_workspace):
    """Test that cache resume works in real search scenarios."""
    orchestrator = SearchOrchestrator(cache_dir=temp_workspace / "search_cache")

    # First search - should hit API
    papers1 = await orchestrator.search_source(
        source="openalex",
        query="test query for cache",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        limit=5,
        resume=False,
    )

    count1 = len(papers1)
    assert count1 > 0

    # Second search - should use cache
    papers2 = await orchestrator.search_source(
        source="openalex",
        query="test query for cache",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        limit=5,
        resume=True,  # Enable resume
    )

    orchestrator.close()

    count2 = len(papers2)

    # Should return same results
    assert count2 == count1

    # Verify paper IDs match
    ids1 = set(p.paper_id for p in papers1)
    ids2 = set(p.paper_id for p in papers2)
    assert ids1 == ids2


@pytest.mark.integration
def test_validation_workflow(temp_workspace):
    """Test data validation at different pipeline stages."""
    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="validation", timestamp=timestamp)

    # Create valid papers
    valid_papers = [
        Paper(
            paper_id=f"valid:paper{i}",
            doi=f"10.1234/valid{i}",
            title=f"Valid Paper {i}",
            authors=[Author(name=f"Author {i}")],
            year=2023,
            citation_count=i,
            external_ids={"doi": f"10.1234/valid{i}"},
            source=source,
        )
        for i in range(5)
    ]

    # Save as phase 1 output
    phase1_file = temp_workspace / "01_search_papers.parquet"
    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in valid_papers])
    df.to_parquet(phase1_file, index=False)

    # Validate
    is_valid = validate_phase_output(
        temp_workspace,
        check_schema=True,
        check_duplicates=False,
        check_citations=False,
        strict=False,
    )

    assert is_valid, "Valid data should pass validation"


@pytest.mark.integration
def test_large_dataset_io(temp_workspace):
    """Test I/O with larger datasets to check performance and correctness."""
    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="large test", timestamp=timestamp)

    # Create a larger dataset
    large_papers = [
        Paper(
            paper_id=f"large:paper{i}",
            doi=f"10.9999/large{i}",
            title=f"Large Dataset Paper {i}",
            authors=[Author(name=f"Author {i}"), Author(name=f"CoAuthor {i}")],
            year=2020 + (i % 5),
            venue="Test Conference",
            abstract=f"Abstract for large dataset paper {i}. " * 10,  # Longer text
            citation_count=i,
            external_ids={"doi": f"10.9999/large{i}"},
            source=source,
        )
        for i in range(100)  # 100 papers
    ]

    # Save to Parquet
    parquet_file = temp_workspace / "large_dataset.parquet"
    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in large_papers])
    df.to_parquet(parquet_file, index=False)

    assert parquet_file.exists()

    # Load and verify
    loaded_df = pd.read_parquet(parquet_file)
    assert len(loaded_df) == len(large_papers)

    # Test filtering and querying
    recent_papers = loaded_df[loaded_df["year"] >= 2023]
    assert len(recent_papers) > 0

    high_cited = loaded_df[loaded_df["citation_count"] >= 50]
    assert len(high_cited) > 0


@pytest.mark.integration
def test_multiple_file_formats_consistency(sample_papers, temp_workspace):
    """Test that data is consistent across different file formats."""

    # Save in multiple formats
    parquet_file = temp_workspace / "papers.parquet"
    csv_file = temp_workspace / "papers.csv"
    bibtex_file = temp_workspace / "papers.bib"

    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in sample_papers])

    df.to_parquet(parquet_file, index=False)
    df.to_csv(csv_file, index=False)

    exporter = BibTeXExporter()
    exporter.export(sample_papers, bibtex_file)

    # Load and compare
    loaded_parquet = pd.read_parquet(parquet_file)
    loaded_csv = pd.read_csv(csv_file)

    # Both should have same number of rows
    assert len(loaded_parquet) == len(loaded_csv) == len(sample_papers)

    # Key fields should match
    assert list(loaded_parquet["paper_id"]) == list(loaded_csv["paper_id"])
    assert list(loaded_parquet["title"]) == list(loaded_csv["title"])

    # BibTeX should contain all papers
    bibtex_content = bibtex_file.read_text(encoding='utf-8')
    for paper in sample_papers:
        assert any(word in bibtex_content for word in paper.title.split()[:3])


@pytest.mark.integration
def test_incremental_save(temp_workspace):
    """Test saving data incrementally (simulating streaming saves)."""
    output_dir = temp_workspace / "incremental"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="incremental", timestamp=timestamp)

    # Simulate saving in batches
    batch_size = 10
    total_batches = 5

    all_paper_ids = []

    for batch_num in range(total_batches):
        batch_papers = [
            Paper(
                paper_id=f"inc:batch{batch_num}_paper{i}",
                title=f"Batch {batch_num} Paper {i}",
                authors=[Author(name=f"Author {i}")],
                year=2023,
                citation_count=i,
                external_ids={"source": source.database},
                source=source,
            )
            for i in range(batch_size)
        ]

        # Save each batch
        batch_file = output_dir / f"batch_{batch_num}.parquet"
        df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in batch_papers])
        df.to_parquet(batch_file, index=False)

        all_paper_ids.extend([p.paper_id for p in batch_papers])

    # Verify all batches saved
    batch_files = list(output_dir.glob("batch_*.parquet"))
    assert len(batch_files) == total_batches

    # Combine all batches
    combined_df = pd.concat([pd.read_parquet(f) for f in batch_files], ignore_index=True)

    assert len(combined_df) == batch_size * total_batches
    assert set(combined_df["paper_id"]) == set(all_paper_ids)


@pytest.mark.integration
def test_citation_io(temp_workspace):
    """Test saving and loading citation data."""
    citations = [
        Reference(
            citing_paper_id=f"paper:{i}",
            cited_paper_id=f"paper:{i+1}",
            source="test",
            context=f"Citation context {i}",
        )
        for i in range(10)
    ]

    # Save citations
    citations_file = temp_workspace / "citations.parquet"
    citations_df = pd.DataFrame([c.model_dump() for c in citations])
    citations_df.to_parquet(citations_file, index=False)

    assert citations_file.exists()

    # Load citations
    loaded_citations = pd.read_parquet(citations_file)

    assert len(loaded_citations) == len(citations)
    assert "citing_paper_id" in loaded_citations.columns
    assert "cited_paper_id" in loaded_citations.columns
    assert "context" in loaded_citations.columns

    # Verify data
    for i, citation in enumerate(citations):
        row = loaded_citations.iloc[i]
        assert row["citing_paper_id"] == citation.citing_paper_id
        assert row["cited_paper_id"] == citation.cited_paper_id


@pytest.mark.integration
def test_workspace_organization(temp_workspace):
    """Test organizing outputs in a structured workspace."""
    # Create directory structure
    search_dir = temp_workspace / "01_search"
    dedup_dir = temp_workspace / "02_dedup"
    enrich_dir = temp_workspace / "03_enrich"

    for dir_path in [search_dir, dedup_dir, enrich_dir]:
        dir_path.mkdir(exist_ok=True)

    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="workspace", timestamp=timestamp)

    # Create sample data
    papers = [
        Paper(
            paper_id=f"ws:paper{i}",
            title=f"Workspace Paper {i}",
            authors=[Author(name=f"Author {i}")],
            year=2023,
            citation_count=i,
            external_ids={"source": source.database},
            source=source,
        )
        for i in range(5)
    ]

    # Save in different directories
    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in papers])

    df.to_parquet(search_dir / "results.parquet", index=False)
    df.to_parquet(dedup_dir / "deduped.parquet", index=False)
    df.to_csv(enrich_dir / "influence.csv", index=False)

    # Verify structure
    assert (search_dir / "results.parquet").exists()
    assert (dedup_dir / "deduped.parquet").exists()
    assert (enrich_dir / "influence.csv").exists()

    # Verify we can load from structured workspace
    search_results = pd.read_parquet(search_dir / "results.parquet")
    dedup_results = pd.read_parquet(dedup_dir / "deduped.parquet")

    assert len(search_results) == len(papers)
    assert len(dedup_results) == len(papers)

