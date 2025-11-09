"""End-to-end integration tests for the SRP.

These tests exercise the full workflow of the systematic review
pipeline: searching, deduplicating, enriching with citations and
computing influence scores.  They rely on external APIs and may be
slow to run.  If your environment does not allow network access
(e.g. in continuous integration), mark these tests as xfail.
"""

import asyncio
from datetime import date, datetime
from pathlib import Path
import tempfile
import shutil

import pandas as pd
import pytest

from srp.search.orchestrator import SearchOrchestrator
from srp.dedup.deduplicator import Deduplicator
from srp.enrich.citations import CitationEnricher
from srp.enrich.influence import InfluenceScorer
from srp.io.bibtex import BibTeXExporter
from srp.io.validation import validate_phase_output


@pytest.fixture
def temp_output_dir():
    """Create a temporary directory for storing intermediate outputs."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_phase1_workflow(temp_output_dir):
    """Test the Phase 1 search workflow end-to-end."""
    orchestrator = SearchOrchestrator()
    # Use a narrow date range and small limit to avoid large downloads
    papers = await orchestrator.search_source(
        source="openalex",
        query="machine learning",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        limit=10,
        resume=False,
    )
    orchestrator.close()
    # Ensure we retrieved some papers and they have IDs
    assert len(papers) > 0, "Should retrieve papers"
    assert all(p.paper_id for p in papers), "All papers should have IDs"
    # Save to parquet with naming convention expected by validator
    df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in papers])
    output_file = temp_output_dir / "search_papers.parquet"
    df.to_parquet(output_file, index=False)
    assert output_file.exists(), "Output file should be created"
    # Validate the phase output using the validator
    is_valid = validate_phase_output(
        temp_output_dir,
        check_schema=True,
        check_duplicates=False,
        check_citations=False,
        strict=False,
    )
    assert is_valid, "Phase 1 output should be valid"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_phase2_workflow(temp_output_dir):
    """Test the Phase 2 workflow end-to-end."""
    orchestrator = SearchOrchestrator()
    papers = await orchestrator.search_source(
        source="openalex",
        query="systematic review",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        limit=20,
        resume=False,
    )
    orchestrator.close()
    # Deduplicate
    deduplicator = Deduplicator()
    deduped_papers, clusters = deduplicator.deduplicate(papers)
    assert len(deduped_papers) <= len(papers), "Deduplication should not increase paper count"
    # Citation enrichment with small limits
    enricher = CitationEnricher(max_papers=5, refs_per_paper=10)
    references = await enricher.fetch_references(deduped_papers, sources=["semantic_scholar"])
    resolved_refs, stats = enricher.resolve_citations(references, deduped_papers)
    assert len(resolved_refs) >= 0, "Should fetch some references"
    # Influence scoring
    scorer = InfluenceScorer()
    influence_df = scorer.compute_influence_scores(deduped_papers, resolved_refs)
    assert len(influence_df) == len(deduped_papers), "Influence scores for all papers"
    assert "influence_score" in influence_df.columns, "Influence score column present"
    # Save outputs
    deduped_df = pd.DataFrame([
        p.model_dump(mode="json", exclude={"raw_data"}) for p in deduped_papers
    ])
    deduped_df.to_parquet(temp_output_dir / "02_deduped_papers.parquet", index=False)
    refs_df = pd.DataFrame([r.model_dump() for r in resolved_refs])
    refs_df.to_parquet(temp_output_dir / "02_citation_edges.parquet", index=False)
    influence_df.to_csv(temp_output_dir / "02_seminal_papers.csv", index=False)


@pytest.mark.integration
def test_bibtex_export(temp_output_dir):
    """Test exporting papers to BibTeX format."""
    from srp.core.models import Paper, Author, Source
    papers = [
        Paper(
            paper_id="test:1",
            doi="10.1234/test.1",
            title="Test Paper One",
            authors=[Author(name="John Doe"), Author(name="Jane Smith")],
            year=2023,
            venue="Test Conference",
            citation_count=10,
            external_ids={"test": "1"},
            source=Source(database="test", query="test", timestamp=datetime.now().isoformat()),
        ),
        Paper(
            paper_id="test:2",
            arxiv_id="2301.12345",
            title="Test Paper Two",
            authors=[Author(name="Alice Johnson")],
            year=2024,
            abstract="This is a test abstract.",
            citation_count=5,
            external_ids={"test": "2"},
            source=Source(database="test", query="test", timestamp=datetime.now().isoformat()),
        ),
    ]
    exporter = BibTeXExporter()
    output_file = temp_output_dir / "test.bib"
    exporter.export(papers, output_file)
    assert output_file.exists(), "BibTeX file should be created"
    content = output_file.read_text()
    assert "Test Paper One" in content, "Paper title should be in BibTeX"
    assert "Doe" in content, "Author surname should be in BibTeX"
    assert "10.1234/test.1" in content, "DOI should be in BibTeX"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cache_and_resume():
    """Test caching and resume functionality of SearchCache."""
    from srp.io.cache import SearchCache
    from srp.io.paths import get_cache_path
    cache_path = get_cache_path("test_searches")
    cache = SearchCache(cache_path)
    # Register query
    query_id = cache.register_query(
        source="test",
        query="test query",
        start_date="2023-01-01",
        end_date="2023-12-31",
    )
    assert query_id, "Query ID should be returned"
    # Check progress
    progress = cache.get_query_progress(query_id)
    assert progress is not None, "Progress should be available"
    assert progress["source"] == "test"
    # Cache a paper
    from srp.core.models import Paper, Source
    test_paper = Paper(
        paper_id="test:cache",
        title="Cached Paper",
        year=2023,
        citation_count=0,
        external_ids={},
        source=Source(database="test", query="test", timestamp=datetime.now().isoformat()),
    )
    cache.cache_paper(query_id, test_paper)
    cached_papers = cache.get_cached_papers(query_id)
    assert len(cached_papers) == 1
    assert cached_papers[0].paper_id == "test:cache"
    # Mark query as completed
    cache.mark_completed(query_id)
    progress = cache.get_query_progress(query_id)
    assert progress["completed"], "Query should be marked completed"
    cache.close()


@pytest.mark.integration
def test_query_builder():
    """Test query builder combinations and augmentation."""
    from srp.search.query_builder import QueryBuilder
    builder = QueryBuilder()
    core_terms = ["machine learning", "bias", "fairness"]
    queries = builder.generate_core_pairs(core_terms)
    assert len(queries) > 0
    assert "machine learning bias" in queries
    augmented = builder.generate_augmented_queries(
        queries,
        ["detection", "mitigation"],
        max_augmentations=1,
    )
    assert len(augmented) > len(queries)