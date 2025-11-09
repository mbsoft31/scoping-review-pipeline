"""Integration tests for Deduplication → Enrichment pipeline flow.

These tests verify that deduplicated papers can be enriched with citations
and influence scores, and that data flows correctly between modules.
"""

import asyncio
from datetime import datetime
from pathlib import Path
import tempfile
import shutil

import pandas as pd
import pytest

from srp.dedup.deduplicator import Deduplicator
from srp.enrich.citations import CitationEnricher
from srp.enrich.influence import InfluenceScorer
from srp.core.models import Paper, Author, Source, Reference


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace for test outputs."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def deduped_papers():
    """Generate a set of deduplicated papers for enrichment testing."""
    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="test query", timestamp=timestamp)

    papers = [
        Paper(
            paper_id="paper:1",
            doi="10.1234/paper1",
            title="Foundations of Systematic Reviews",
            authors=[Author(name="Alice Smith"), Author(name="Bob Jones")],
            year=2020,
            venue="Review Methods Journal",
            abstract="Comprehensive guide to systematic review methodology.",
            citation_count=150,
            external_ids={"doi": "10.1234/paper1", "openalex": "W1"},
            source=source,
        ),
        Paper(
            paper_id="paper:2",
            doi="10.1234/paper2",
            title="Machine Learning for Evidence Synthesis",
            authors=[Author(name="Carol White"), Author(name="David Brown")],
            year=2022,
            venue="AI in Research Conference",
            abstract="Applying ML techniques to automate systematic reviews.",
            citation_count=85,
            external_ids={"doi": "10.1234/paper2", "openalex": "W2"},
            source=source,
        ),
        Paper(
            paper_id="paper:3",
            doi="10.1234/paper3",
            title="Advanced Citation Analysis Methods",
            authors=[Author(name="Eve Johnson")],
            year=2023,
            venue="Bibliometrics Quarterly",
            abstract="New approaches to analyzing citation networks.",
            citation_count=42,
            external_ids={"doi": "10.1234/paper3", "openalex": "W3"},
            source=source,
        ),
    ]
    return papers


@pytest.mark.integration
@pytest.mark.asyncio
async def test_citation_enrichment_flow(deduped_papers, temp_workspace):
    """Test enriching papers with citation data."""
    # Initialize enricher with limits for testing
    enricher = CitationEnricher(max_papers=3, refs_per_paper=10)

    # Fetch references
    references = await enricher.fetch_references(
        deduped_papers,
        sources=["semantic_scholar", "openalex"]
    )

    # Should get some references (may be empty if APIs are unavailable)
    assert isinstance(references, list), "References should be a list"

    # Resolve citations
    resolved_refs, stats = enricher.resolve_citations(references, deduped_papers)

    assert isinstance(resolved_refs, list), "Resolved refs should be a list"
    assert isinstance(stats, dict), "Stats should be a dictionary"

    # Verify stats structure (actual keys returned by implementation)
    assert "total_references" in stats
    assert "in_corpus_citations" in stats
    assert "external_citations" in stats
    assert "cited_papers" in stats

    # Save results
    if len(resolved_refs) > 0:
        refs_output = temp_workspace / "citation_edges.parquet"
        refs_df = pd.DataFrame([r.model_dump() for r in resolved_refs])
        refs_df.to_parquet(refs_output, index=False)

        assert refs_output.exists()

        # Verify citation structure
        loaded_refs = pd.read_parquet(refs_output)
        assert "citing_paper_id" in loaded_refs.columns
        assert "cited_paper_id" in loaded_refs.columns


@pytest.mark.integration
def test_influence_scoring(deduped_papers):
    """Test computing influence scores for papers."""
    scorer = InfluenceScorer()

    # Create some mock citations between papers
    citations = [
        Reference(
            citing_paper_id="paper:2",
            cited_paper_id="paper:1",
            source="test",
            context="",
        ),
        Reference(
            citing_paper_id="paper:3",
            cited_paper_id="paper:1",
            source="test",
            context="",
        ),
        Reference(
            citing_paper_id="paper:3",
            cited_paper_id="paper:2",
            source="test",
            context="",
        ),
    ]

    # Compute influence scores
    influence_df = scorer.compute_influence_scores(deduped_papers, citations)

    # Verify output
    assert len(influence_df) == len(deduped_papers), "Should have score for each paper"
    assert "paper_id" in influence_df.columns
    assert "influence_score" in influence_df.columns

    # Paper 1 is cited by both 2 and 3, should have highest influence
    paper1_score = influence_df[influence_df["paper_id"] == "paper:1"]["influence_score"].values[0]
    paper3_score = influence_df[influence_df["paper_id"] == "paper:3"]["influence_score"].values[0]

    assert paper1_score > paper3_score, "Most cited paper should have higher influence"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_dedup_to_enrich_flow(temp_workspace):
    """Test complete flow: Dedup → Citation Enrichment → Influence Scoring."""
    from datetime import datetime

    # Step 1: Create test papers with duplicates
    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="test", timestamp=timestamp)

    papers = [
        Paper(
            paper_id="orig:1",
            doi="10.1111/orig1",
            title="Original Paper One",
            authors=[Author(name="Author A")],
            year=2023,
            citation_count=10,
            external_ids={"doi": "10.1111/orig1"},
            source=source,
        ),
        Paper(
            paper_id="dup:1",
            doi="10.1111/orig1",  # Same DOI - duplicate
            title="Original paper one",  # Different case
            authors=[Author(name="Author A")],
            year=2023,
            citation_count=10,
            external_ids={"doi": "10.1111/orig1"},
            source=source,
        ),
        Paper(
            paper_id="orig:2",
            doi="10.2222/orig2",
            title="Original Paper Two",
            authors=[Author(name="Author B")],
            year=2023,
            citation_count=5,
            external_ids={"doi": "10.2222/orig2"},
            source=source,
        ),
    ]

    # Step 2: Deduplicate
    deduplicator = Deduplicator()
    deduped_papers, clusters = deduplicator.deduplicate(papers)

    assert len(deduped_papers) == 2, "Should have 2 unique papers"

    # Save deduped papers
    dedup_output = temp_workspace / "02_deduped_papers.parquet"
    df_dedup = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in deduped_papers])
    df_dedup.to_parquet(dedup_output, index=False)

    # Step 3: Citation enrichment (with small limits)
    enricher = CitationEnricher(max_papers=2, refs_per_paper=5)
    references = await enricher.fetch_references(deduped_papers, sources=["semantic_scholar"])
    resolved_refs, stats = enricher.resolve_citations(references, deduped_papers)

    # Save citations if any were found
    if len(resolved_refs) > 0:
        refs_output = temp_workspace / "03_citation_edges.parquet"
        refs_df = pd.DataFrame([r.model_dump() for r in resolved_refs])
        refs_df.to_parquet(refs_output, index=False)
        assert refs_output.exists()

    # Step 4: Compute influence scores
    scorer = InfluenceScorer()
    influence_df = scorer.compute_influence_scores(deduped_papers, resolved_refs)

    assert len(influence_df) == len(deduped_papers)

    # Save influence scores
    influence_output = temp_workspace / "04_influence_scores.csv"
    influence_df.to_csv(influence_output, index=False)

    assert influence_output.exists()

    # Verify all outputs exist
    assert dedup_output.exists()
    assert influence_output.exists()

    # Verify data consistency
    loaded_dedup = pd.read_parquet(dedup_output)
    loaded_influence = pd.read_csv(influence_output)

    assert len(loaded_dedup) == len(loaded_influence)


@pytest.mark.integration
def test_enrichment_preserves_paper_data(deduped_papers):
    """Ensure enrichment doesn't modify original paper data."""
    import copy

    original_papers = copy.deepcopy(deduped_papers)

    # Compute influence scores
    scorer = InfluenceScorer()
    influence_df = scorer.compute_influence_scores(deduped_papers, [])

    # Verify original papers weren't modified
    for orig, current in zip(original_papers, deduped_papers):
        assert orig.paper_id == current.paper_id
        assert orig.title == current.title
        assert orig.doi == current.doi
        assert orig.year == current.year


@pytest.mark.integration
def test_influence_with_no_citations(deduped_papers):
    """Test influence scoring when there are no citations."""
    scorer = InfluenceScorer()
    influence_df = scorer.compute_influence_scores(deduped_papers, [])

    # Should still return scores (likely based on citation_count or zero)
    assert len(influence_df) == len(deduped_papers)
    assert "influence_score" in influence_df.columns


@pytest.mark.integration
@pytest.mark.asyncio
async def test_citation_enrichment_error_handling(deduped_papers):
    """Test that citation enrichment handles errors gracefully."""
    enricher = CitationEnricher(max_papers=1, refs_per_paper=5)

    # Test with papers that have no external IDs that APIs can use
    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="test", timestamp=timestamp)

    invalid_papers = [
        Paper(
            paper_id="invalid:1",
            title="Paper Without External IDs",
            authors=[Author(name="Unknown")],
            year=2023,
            citation_count=0,
            external_ids={},  # No DOI, arXiv, etc.
            source=source,
        )
    ]

    # Should not crash, just return empty or minimal results
    try:
        references = await enricher.fetch_references(invalid_papers, sources=["semantic_scholar"])
        resolved_refs, stats = enricher.resolve_citations(references, invalid_papers)

        assert isinstance(resolved_refs, list)
        assert isinstance(stats, dict)
    except Exception as e:
        pytest.fail(f"Enrichment should handle missing IDs gracefully, but raised: {e}")


@pytest.mark.integration
def test_influence_scoring_with_self_citations(deduped_papers):
    """Test that self-citations are handled properly."""
    # Create a self-citation
    citations = [
        Reference(
            citing_paper_id="paper:1",
            cited_paper_id="paper:1",  # Self-citation
            source="test",
            context="",
        ),
        Reference(
            citing_paper_id="paper:2",
            cited_paper_id="paper:1",
            source="test",
            context="",
        ),
    ]

    scorer = InfluenceScorer()
    influence_df = scorer.compute_influence_scores(deduped_papers, citations)

    # Should handle self-citations without errors
    assert len(influence_df) == len(deduped_papers)
    assert "influence_score" in influence_df.columns


@pytest.mark.integration
@pytest.mark.asyncio
async def test_batch_citation_enrichment(temp_workspace):
    """Test enrichment with larger batch of papers."""
    from datetime import datetime

    # Create a larger set of papers
    timestamp = datetime.now().isoformat()
    source = Source(database="test", query="batch test", timestamp=timestamp)

    papers = []
    for i in range(10):
        papers.append(
            Paper(
                paper_id=f"batch:paper{i}",
                doi=f"10.9999/batch{i}",
                title=f"Batch Test Paper {i}",
                authors=[Author(name=f"Author {i}")],
                year=2023,
                citation_count=i,
                external_ids={"doi": f"10.9999/batch{i}"},
                source=source,
            )
        )

    # Enrich with limited scope
    enricher = CitationEnricher(max_papers=5, refs_per_paper=3)
    references = await enricher.fetch_references(papers, sources=["semantic_scholar"])
    resolved_refs, stats = enricher.resolve_citations(references, papers)

    # Compute influence
    scorer = InfluenceScorer()
    influence_df = scorer.compute_influence_scores(papers, resolved_refs)

    assert len(influence_df) == len(papers), "Should have scores for all papers"

    # Save results
    output_file = temp_workspace / "batch_influence.csv"
    influence_df.to_csv(output_file, index=False)

    assert output_file.exists()

    # Verify sorting capability
    sorted_by_influence = influence_df.sort_values("influence_score", ascending=False)
    assert len(sorted_by_influence) == len(papers)

