# Search Module

The **search** module is responsible for querying external scholarly databases, generating systematic search queries and orchestrating concurrent requests.  It abstracts away the details of each data source and provides a unified interface for retrieving `Paper` objects.

## Components

### Base Client

The base class for all search clients is defined in [`base.py`](../../src/srp/search/base.py).  The `SearchClient` abstract class defines the following methods:

- `async search(query: str, start_date: Optional[date], end_date: Optional[date], limit: Optional[int], **kwargs) -> List[Paper]`: Performs an asynchronous search for papers matching the query within a date range.  Derived clients implement pagination and rate limiting.
- `close() -> None`: Cleanly shuts down any underlying HTTP sessions.

Derived classes must implement the `search()` method to fetch results from their respective APIs and return a list of `Paper` instances.

### Adapters

Each data source is implemented as a separate client under the [`adapters`](../../src/srp/search/adapters) subpackage:

- **OpenAlexClient** (`openalex.py`): Queries the [OpenAlex API](https://docs.openalex.org) with CORD‑19‑style search strings.  Supports pagination and rate limiting via an `aiolimiter` token bucket.  Parses OpenAlex JSON results into `Paper` objects.
- **SemanticScholarClient** (`semantic_scholar.py`): Interfaces with the Semantic Scholar API.  Handles API key injection if provided via environment variables, supports offset pagination and customizable page size.  Extracts metadata and citation counts from the response.
- **CrossrefClient** (`crossref.py`): Wraps the Crossref REST API.  It applies polite pooling by including a user email in requests, supports filtering by publication dates and deals with rate limits via exponential backoff.  Parses Crossref records into `Paper` instances.
- **ArxivClient** (`arxiv.py`): Executes searches against the arXiv API.  Builds combined queries across categories and terms, handles atom feed pagination via `start` and `max_results`, and extracts titles, abstracts, categories, DOIs and PDF links.

All clients inherit from `SearchClient` and share a common signature for the `search()` method, making it easy to add new sources.

### Query Builder

[`query_builder.py`](../../src/srp/search/query_builder.py) contains helper functions for constructing systematic search queries.  It provides:

- `generate_systematic_queries(core_terms: List[str], method_terms: List[str], context_terms: List[str]) -> List[str]`: Produces a list of conjunctive/disjunctive search strings by combining core concepts, methodological keywords and contextual terms.
- `load_domain_terms(domain: str) -> Dict[str, List[str]]`: Loads predefined term templates from `config/defaults.yaml` for common domains (e.g. AI fairness, climate adaptation).
- `QueryBuilder` class: An object‑oriented wrapper around these functions that also supports random sampling of term combinations.

### Orchestrator

The [`orchestrator.py`](../../src/srp/search/orchestrator.py) module defines `SearchOrchestrator`, which coordinates parallel searches across multiple databases and caches results using an SQLite backend.  Key methods include:

- `async search_source(source: str, query: str, start_date: date, end_date: date, limit: Optional[int], config: Optional[dict], resume: bool) -> List[Paper]`: Executes a search against a single source.  It checks the cache to avoid re‑fetching pages, handles pagination and merges results into the local cache.
- `close() -> None`: Closes all HTTP sessions.

The orchestrator uses a `SearchCache` (see the `io` module) to persist search queries and partial results, enabling resumable searches.

## Usage

To run a search from the CLI, use the `phase1` command:

```bash
srp phase1 --query "diabetes RCT" --db openalex,semantic_scholar --limit 500
```

This will invoke the orchestrator with the specified query and databases, save results to a timestamped directory under `output/`, and produce both Parquet and CSV files of the retrieved papers.

Programmatically, you can instantiate the orchestrator and call `search_source()` directly:

```python
from srp.search.orchestrator import SearchOrchestrator

orch = SearchOrchestrator()
papers = await orch.search_source(
    source="openalex",
    query="machine learning healthcare",
    start_date=date(2015, 1, 1),
    end_date=date(2023, 12, 31),
    limit=100,
    config={"page_size": 25},
    resume=True,
)
orch.close()
```

The returned `papers` list contains `Paper` instances ready for further processing.