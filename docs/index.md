# Systematic Review Pipeline Documentation

Welcome to the documentation for the **Systematic Review Pipeline (SRP)**.  This open‑source project aims to provide researchers with a modular, end‑to‑end toolchain for conducting systematic literature reviews.  It supports everything from retrieving papers across multiple scholarly databases through deduplication, screening, data extraction, quality assessment and meta‑analysis, to presenting results via a web dashboard and command‑line interface.  Each module of the pipeline lives under the `src/srp` package and exposes a clear API for extension and integration.

This documentation is organised by module.  Each subfolder in the `docs/` directory corresponds to a top‑level module in `src/srp`.  Inside each folder you will find a `README.md` describing the purpose of the module, its key classes and functions, and any relevant usage notes or API specifications.

## Modules overview

| Module | Summary |
|-------|---------|
| [`core`](core/README.md) | Fundamental data models (`Paper`, `Author`, `Source`) and helper functions for ID normalization and metadata cleanup. |
| [`search`](search/README.md) | Clients and orchestration for querying external scholarly databases (OpenAlex, Semantic Scholar, Crossref, arXiv) and building systematic queries. |
| [`dedup`](dedup/README.md) | Multi‑pass deduplication engine that groups duplicate records using DOIs, arXiv IDs and fuzzy title matching. |
| [`enrich`](enrich/README.md) | Citation enrichment and influence scoring to build citation networks and rank seminal papers. |
| [`extraction`](extraction/README.md) | NLP‑powered data extraction from full‑text articles to pull out study design, sample sizes, outcomes and statistics. |
| [`quality`](quality/README.md) | Automated risk‑of‑bias assessment using configurable tools such as RoB 2 and Newcastle‑Ottawa. |
| [`meta`](meta/README.md) | Statistical meta‑analysis and forest plot generation for quantitative synthesis. |
| [`screening`](screening/README.md) | Semantic matching, auto‑screening, active learning and human‑in‑the‑loop screening workflows. |
| [`collab`](collab/README.md) | Collaborative workspace management for multi‑reviewer workflows and conflict resolution. |
| [`living`](living/README.md) | Scheduling and automation for living systematic reviews with periodic updates and notifications. |
| [`prisma`](prisma/README.md) | PRISMA flow diagram generation from pipeline outputs. |
| [`web`](web/README.md) | FastAPI web application, routes and Jinja2 templates for an interactive dashboard. |
| [`cli`](cli/README.md) | Typer‑based command‑line interface for interacting with the pipeline. |
| [`config`](config/README.md) | Environment configuration and default settings management. |
| [`io`](io/README.md) | I/O utilities for caching, exporting and validating data. |
| [`utils`](utils/README.md) | Miscellaneous helpers such as rate limiting and structured logging. |

Refer to each module’s documentation for detailed API descriptions.