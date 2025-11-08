# Enrichment Module

The **enrich** module augments the deduplicated corpus with citation information and computes influence scores.  After searching and deduplicating papers, enrichment helps identify which works are seminal and how they relate to each other via citations.

## Citation Enrichment

The [`citations.py`](../../src/srp/enrich/citations.py) module defines the `CitationEnricher` class.  It works as follows:

1. **Prioritise papers** – Since querying citations for every paper can be expensive, the enricher ranks papers by citation count (e.g. top 200) and processes them first.  The `max_papers` parameter controls how many papers to enrich.
2. **Fetch references** – The enricher queries external services (Semantic Scholar or OpenAlex) to fetch the references (citations) of each paper.  It uses the DOI when available.  A reference is captured as a `Reference` object containing the cited DOI and year.
3. **Resolve citations** – A mapping from DOIs to in‑corpus paper IDs is constructed.  References that match DOIs in the corpus are considered in‑corpus citations.  Edges between citing and cited papers are recorded, producing a citation graph.
4. **Compute statistics** – For each paper, the enricher computes summary statistics such as the number of in‑corpus and out‑of‑corpus references and the proportion of resolved citations.

### API

```python
from srp.enrich.citations import CitationEnricher

enricher = CitationEnricher(max_papers=200, sources=["semantic_scholar", "openalex"])
results = await enricher.enrich(papers)

edges = results.edges  # list of (citing_id, cited_id)
citation_stats = results.stats  # mapping from paper_id to summary stats
```

The enrichment process is asynchronous and should be awaited.  Papers passed to `enrich()` must have canonical IDs (deduplicated) to avoid self‑citations.

## Influence Scoring

The [`influence.py`](../../src/srp/enrich/influence.py) module provides the `InfluenceScorer` class.  It builds a directed graph of citations and computes various centrality measures:

- **PageRank** – A global measure of influence based on the probability of reaching a paper through random citation surfing.
- **In‑degree** – Counts how many in‑corpus citations a paper receives.
- **Betweenness centrality** – Measures how often a paper lies on shortest paths between other papers, capturing bridging importance.
- **Raw citation counts** – Incorporates external citation counts from the metadata.

Each measure is z‑score normalised and combined into an overall influence score using configurable weights.  The default weights are defined in `config/defaults.yaml`.  The scorer returns a sorted list of papers with their scores and component metrics.

### API

```python
from srp.enrich.influence import InfluenceScorer

scorer = InfluenceScorer(weights={"pagerank":0.4, "in_degree":0.3, "betweenness":0.2, "citations":0.1})
ranked = scorer.score(papers, edges)

for paper, score in ranked[:10]:
    print(paper.title, score.overall)
```

## CLI integration

During Phase 2 of the pipeline, the CLI invokes both the citation enricher and influence scorer.  Results are saved to files such as `citation_edges.parquet`, `influence_scores.csv` and `citation_stats.json`.  The top 10 influential papers are printed to the console.