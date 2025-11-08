# Systematic Review Pipeline

This project implements a modular, end‑to‑end pipeline for systematic literature
reviews.  It consists of two phases:

1. **Phase 1 – Search:**  Query multiple scholarly databases (OpenAlex,
   Semantic Scholar, etc.), apply rate limiting and retry logic, and
   persist results in Parquet/CSV format.  A query builder can generate
   systematic search terms based on domain templates.  Caching allows
   searches to be resumed without losing progress.

2. **Phase 2 – Analysis:**  Deduplicate the collected papers using a
   multi‑strategy matching approach (DOI/arXiv/fuzzy title), enrich the
   corpus with citation data from external APIs, construct a citation
   network, compute multi‑component influence scores, and export
   ranked seminal papers along with graph statistics.

The code under `src/srp/` contains reusable components for each
sub‑task (configuration, models, search adapters, deduplication,
citation enrichment, influence scoring, and CLI).  Tests live in
`tests/` and can be executed with `pytest`.

## Screening (Phase 1.5)

Between the search and analysis phases you can optionally perform
**semantic screening** (Phase 1.5) to filter the corpus according to
domain‑specific inclusion and exclusion criteria.  The screening
subsystem uses sentence‑transformer models to compute semantic
similarities between paper titles/abstracts and natural‑language
queries.  You can specify strict mandatory criteria, assign weights
to criteria, and define domain vocabularies for tagging.  Screening
supports four modes:

* **auto** – fully automatic decisions based on confidence thresholds;
* **semi_auto** – uncertain papers are queued for human review;
* **hitl** – human‑in‑the‑loop; every uncertain or low‑confidence
  decision is reviewed;
* **manual** – no automatic screening; all papers require manual
  decisions.

Screening results are saved to a new ``phase1.5_*`` directory and,
when using semi‑automatic or HITL modes, a review queue is created
for later adjudication via the CLI.

## Getting started

To set up a virtual environment and install dependencies, run:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

To run Phase 1 against OpenAlex:

```bash
python -m srp.cli.main phase1 --query "machine learning fairness" --db openalex
```

To run Phase 2 using the results from a previous search:

```bash
python -m srp.cli.main phase2 output/phase1_YYYYMMDD_HHMMSS
```

See the CLI help (`python -m srp.cli.main --help`) for all options.
