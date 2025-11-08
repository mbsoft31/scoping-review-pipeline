# Deduplication Module

The **dedup** module provides logic to identify and merge duplicate bibliographic records.  When retrieving papers from multiple data sources, duplicates can arise due to overlapping coverage (e.g. the same article indexed in OpenAlex and Crossref).  Deduplication ensures that each unique paper appears only once in the final corpus while preserving relevant metadata from duplicates.

## Deduplicator

The heart of the deduplication module is the `Deduplicator` class implemented in [`deduplicator.py`](../../src/srp/dedup/deduplicator.py).  It performs multiple passes over the input records:

1. **Exact DOI match** – All papers with the same normalised DOI are grouped together.  The DOI normalisation is handled by `core.ids.normalize_doi()`.  If a canonical DOI is missing, the next pass is attempted.
2. **Exact arXiv ID match** – For preprints on arXiv, the arXiv identifier is normalised via `normalize_arxiv_id()` and duplicates are grouped accordingly.
3. **Fuzzy title + year match** – Remaining ungrouped records are compared using a fuzzy string similarity (RapidFuzz’s token set ratio) on the normalised titles.  If the similarity exceeds a threshold (default 90 %), they are considered duplicates.  Publication year is used as an additional constraint to avoid merging unrelated works.

### Merging strategy

For each cluster of duplicates, the deduplicator selects a *canonical record*.  It prefers papers with the most complete metadata (e.g. with a DOI, abstract and venue) and, if available, a higher citation count.  Duplicate records are merged by filling in missing fields from other members.  A mapping from duplicate paper IDs to canonical IDs is produced, along with cluster summaries (see `DeduplicationCluster` in `core.models`).

### API

```python
from srp.dedup.deduplicator import Deduplicator

deduper = Deduplicator(fuzzy_threshold=90)
clusters, canonical_map = deduper.deduplicate(papers)
```

Where `papers` is a list of `Paper` objects.  The `deduplicate()` method returns:

- `clusters`: a list of `DeduplicationCluster` objects, each containing a canonical ID and a list of duplicate IDs.
- `canonical_map`: a dictionary mapping every duplicate paper ID to its canonical paper ID.

After deduplication, you can obtain the deduplicated list of papers by selecting one paper per cluster and merging metadata.

### CLI integration

The `phase2` command of the CLI invokes the deduplicator automatically when processing Phase 1 results.  The deduplicated papers are saved to `deduplicated_papers.parquet` along with a `duplicate_map.csv` containing the duplicate→canonical mapping.

## Extensibility

The deduplication thresholds and matching logic can be customised via constructor arguments.  You can adjust the fuzzy similarity threshold or supply your own scoring function by subclassing `Deduplicator` and overriding `_fuzzy_similarity()`.