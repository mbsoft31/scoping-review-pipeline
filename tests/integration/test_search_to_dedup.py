"""Integration tests for Search → Deduplication pipeline flow.

These tests verify that papers from search can be properly deduplicated
and that the data flows correctly between modules.
"""

import asyncio
from datetime import date, datetime
from pathlib import Path
import tempfile
import shutil

import pandas as pd
import pytest

from srp.search.orchestrator import SearchOrchestrator
from srp.search.base import SearchClient
from srp.dedup.deduplicator import Deduplicator
from srp.core.models import Paper, Author, Source
from srp.io.validation import validate_phase_output


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for test outputs."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_papers():
    """Generate sample papers with potential duplicates for testing."""
    from datetime import datetime

    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="test query", timestamp=timestamp)

    papers = [
        # Paper 1 - Original
        Paper(
            paper_id="openalex:W12345",
            doi="10.1234/test.2024.001",
            title="Machine Learning for Systematic Reviews",
            authors=[Author(name="John Doe"), Author(name="Jane Smith")],
            year=2024,
            venue="AI Conference",
            abstract="This paper presents a novel approach to systematic reviews using ML.",
            citation_count=15,
            external_ids={"openalex": "W12345", "doi": "10.1234/test.2024.001"},
            source=source,
        ),
        # Paper 2 - Duplicate with slight title variation
        Paper(
            paper_id="semantic_scholar:S67890",
            doi="10.1234/test.2024.001",  # Same DOI
            title="Machine learning for systematic reviews",  # Different case
            authors=[Author(name="J. Doe"), Author(name="J. Smith")],
            year=2024,
            venue="AI Conference",
            abstract="This paper presents a novel approach to systematic reviews using ML.",
            citation_count=15,
            external_ids={"semantic_scholar": "S67890", "doi": "10.1234/test.2024.001"},
            source=source,
        ),
        # Paper 3 - Unique paper
        Paper(
            paper_id="openalex:W54321",
            doi="10.5678/another.2024.002",
            title="Deep Learning Applications in Healthcare",
            authors=[Author(name="Alice Johnson")],
            year=2024,
            venue="Medical AI Journal",
            abstract="Survey of deep learning techniques in medical diagnosis.",
            citation_count=8,
            external_ids={"openalex": "W54321", "doi": "10.5678/another.2024.002"},
            source=source,
        ),
        # Paper 4 - Similar title but different paper (no DOI overlap)
        Paper(
            paper_id="arxiv:2401.12345",
            arxiv_id="2401.12345",
            title="Machine Learning in Systematic Review Processes",
            authors=[Author(name="Bob Wilson")],
            year=2024,
            abstract="Different approach to ML in systematic reviews.",
            citation_count=3,
            external_ids={"arxiv": "2401.12345"},
            source=source,
        ),
    ]
    return papers


@pytest.mark.integration
def test_dedup_sample_papers(sample_papers, temp_workspace):
    """Test deduplication with known duplicate papers."""
    deduplicator = Deduplicator()

    # Deduplicate
    deduped_papers, clusters = deduplicator.deduplicate(sample_papers)

    # Assertions
    assert len(deduped_papers) < len(sample_papers), "Should remove duplicates"
    assert len(deduped_papers) == 3, "Should have 3 unique papers (papers 1&2 are duplicates)"
    assert len(clusters) >= 1, "Should have at least one cluster"

    # Verify the duplicate was detected
    doi_papers = [p for p in sample_papers if p.doi == "10.1234/test.2024.001"]
    assert len(doi_papers) == 2, "Two papers share the same DOI"

    deduped_dois = [p.doi for p in deduped_papers if p.doi]
    assert deduped_dois.count("10.1234/test.2024.001") == 1, "Duplicate DOI removed"

    # Save results
    output_file = temp_workspace / "deduped_papers.parquet"
    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in deduped_papers])
    df.to_parquet(output_file, index=False)

    assert output_file.exists()

    # Verify we can read it back
    loaded_df = pd.read_parquet(output_file)
    assert len(loaded_df) == len(deduped_papers)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_then_dedup_flow(temp_workspace):
    """Test complete flow: Search → Save → Dedup → Save."""
    # Step 1: Search
    orchestrator = SearchOrchestrator()
    papers = await orchestrator.search_source(
        source="openalex",
        query="systematic review automation",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        limit=15,
        resume=False,
    )
    orchestrator.close()

    assert len(papers) > 0, "Should retrieve papers from search"
    initial_count = len(papers)

    # Step 2: Save search results
    search_output = temp_workspace / "01_search_results.parquet"
    df_search = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in papers])
    df_search.to_parquet(search_output, index=False)

    assert search_output.exists()

    # Step 3: Deduplicate
    deduplicator = Deduplicator()
    deduped_papers, clusters = deduplicator.deduplicate(papers)

    assert len(deduped_papers) <= initial_count, "Dedup should not increase count"

    # Step 4: Save deduped results
    dedup_output = temp_workspace / "02_deduped_papers.parquet"
    df_dedup = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in deduped_papers])
    df_dedup.to_parquet(dedup_output, index=False)

    assert dedup_output.exists()

    # Step 5: Validate both outputs
    is_valid_search = validate_phase_output(
        temp_workspace,
        check_schema=True,
        check_duplicates=False,
        check_citations=False,
        strict=False,
    )
    assert is_valid_search, "Search output should be valid"

    # Verify data integrity
    loaded_search = pd.read_parquet(search_output)
    loaded_dedup = pd.read_parquet(dedup_output)

    assert len(loaded_search) == initial_count
    assert len(loaded_dedup) == len(deduped_papers)
    assert "paper_id" in loaded_dedup.columns
    assert "title" in loaded_dedup.columns


@pytest.mark.integration
def test_dedup_preserves_metadata(sample_papers):
    """Ensure deduplication preserves important metadata."""
    deduplicator = Deduplicator()
    deduped_papers, _ = deduplicator.deduplicate(sample_papers)

    # Check that all deduped papers have required fields
    for paper in deduped_papers:
        assert paper.paper_id is not None
        assert paper.title is not None
        assert paper.year is not None
        assert paper.source is not None
        assert isinstance(paper.external_ids, dict)

        # Verify authors are preserved
        if paper.authors:
            assert all(hasattr(author, 'name') for author in paper.authors)


@pytest.mark.integration
def test_dedup_cluster_analysis(sample_papers):
    """Test that cluster information is meaningful."""
    deduplicator = Deduplicator()
    deduped_papers, clusters = deduplicator.deduplicate(sample_papers)

    # Analyze clusters
    for cluster in clusters:
        # Cluster is a DeduplicationCluster object with canonical_id and duplicate_ids
        total_papers_in_cluster = 1 + len(cluster.duplicate_ids)  # canonical + duplicates
        assert total_papers_in_cluster >= 2, "A cluster should have at least 2 papers"

        # Papers in a cluster should share some identifier
        all_ids = [cluster.canonical_id] + cluster.duplicate_ids
        cluster_papers = [p for p in sample_papers if p.paper_id in all_ids]

        # Check if they share DOI or have similar titles based on match_type
        if cluster.match_type == "doi":
            dois = [p.doi for p in cluster_papers if p.doi]
            if len(dois) > 1:
                # If multiple DOIs present, they should be the same
                assert len(set(dois)) == 1, "Papers in DOI cluster should share the same DOI"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multi_source_search_and_dedup(temp_workspace, monkeypatch):
    """Test searching from multiple sources and deduplicating combined results."""

    query = "machine learning"
    timestamp = datetime.utcnow().isoformat()

    def build_stub_paper(source_name: str, idx: int, doi: str) -> Paper:
        return Paper(
            paper_id=f"{source_name}:paper{idx}",
            doi=doi,
            title=f"{source_name.title()} Paper {idx}",
            authors=[Author(name=f"{source_name.title()} Author {idx}")],
            year=2024,
            citation_count=idx + 5,
            external_ids={"doi": doi},
            source=Source(database=source_name, query=query, timestamp=timestamp),
        )

    shared_dois = [f"10.5555/ms-shared-{i}" for i in range(3)]
    openalex_dois = shared_dois + [f"10.5555/ms-openalex-{i}" for i in range(5)]
    semantic_dois = shared_dois + [f"10.5555/ms-semantic-{i}" for i in range(5)]

    stub_data = {
        "openalex": [build_stub_paper("openalex", idx, doi) for idx, doi in enumerate(openalex_dois)],
        "semantic_scholar": [
            build_stub_paper("semantic_scholar", idx, doi) for idx, doi in enumerate(semantic_dois)
        ],
    }

    def make_stub_client(source_name: str):
        source_papers = stub_data[source_name]

        class _StubClient(SearchClient):
            def __init__(self, config=None):
                super().__init__(config or {})

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                await self.close()
                return False

            async def close(self):
                return None

            async def search(
                self,
                query,
                start_date=None,
                end_date=None,
                limit=None,
                cursor=None,
                page=None,
            ):
                yielded = 0
                for paper in source_papers:
                    if limit and yielded >= limit:
                        break
                    yield paper
                    yielded += 1

        return _StubClient

    # Patch orchestrator clients to keep the test deterministic/offline.
    monkeypatch.setitem(SearchOrchestrator.CLIENT_MAP, "openalex", make_stub_client("openalex"))
    monkeypatch.setitem(
        SearchOrchestrator.CLIENT_MAP, "semantic_scholar", make_stub_client("semantic_scholar")
    )

    orchestrator = SearchOrchestrator(cache_dir=temp_workspace / "cache")

    # Search from multiple sources
    sources = ["openalex", "semantic_scholar"]
    all_papers = []

    for source in sources:
        try:
            papers = await orchestrator.search_source(
                source=source,
                query=query,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31),
                limit=10,
                resume=False,
            )
            all_papers.extend(papers)
        except Exception as e:
            # Some sources might fail, continue with others
            print(f"Warning: {source} search failed: {e}")
            continue

    orchestrator.close()

    if len(all_papers) == 0:
        pytest.skip("No papers retrieved from any source")

    initial_count = len(all_papers)
    assert initial_count > 0

    # Deduplicate combined results
    deduplicator = Deduplicator()
    deduped_papers, clusters = deduplicator.deduplicate(all_papers)

    # When combining multiple sources, we expect some duplicates
    assert len(deduped_papers) <= initial_count

    # Save combined results
    output_file = temp_workspace / "multi_source_deduped.parquet"
    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in deduped_papers])
    df.to_parquet(output_file, index=False)

    assert output_file.exists()

    # Verify source diversity
    sources_present = set()
    for paper in deduped_papers:
        if paper.source and paper.source.database:
            sources_present.add(paper.source.database)

    # We should have papers from at least one source
    assert len(sources_present) >= 1


@pytest.mark.integration
def test_dedup_empty_input():
    """Test that deduplicator handles empty input gracefully."""
    deduplicator = Deduplicator()
    deduped_papers, clusters = deduplicator.deduplicate([])

    assert len(deduped_papers) == 0
    assert len(clusters) == 0


@pytest.mark.integration
def test_dedup_single_paper(sample_papers):
    """Test deduplication with a single paper."""
    deduplicator = Deduplicator()
    single_paper = [sample_papers[0]]

    deduped_papers, clusters = deduplicator.deduplicate(single_paper)

    assert len(deduped_papers) == 1
    assert deduped_papers[0].paper_id == sample_papers[0].paper_id
    assert len(clusters) == 0, "No clusters with single paper"

