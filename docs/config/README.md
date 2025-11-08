# Configuration Module

The **config** module manages application settings and default parameters.  It uses Pydantic’s `BaseSettings` to load configuration from environment variables, `.env` files and default values.

## Settings

[`settings.py`](../../src/srp/config/settings.py) defines the `Settings` class.  It includes fields for:

- API keys and rate limits for external services (OpenAlex, Semantic Scholar, Crossref, etc.).
- Default date filters (`default_start_date`, `default_end_date`).
- Output and cache directories.
- Logging configuration (JSON vs. plain text).
- Limits for citation enrichment and influence scoring.

Upon instantiation, the settings class loads values from the environment, falling back to sensible defaults.  For example, the OpenAlex API key can be set via the `OPENALEX_API_KEY` environment variable.  Paths such as `output_dir` and `cache_dir` are ensured to exist by the `Settings` constructor.

### Defaults YAML

[`defaults.yaml`](../../src/srp/config/defaults.yaml) stores domain templates for query generation and weights for influence scoring.  For example, the `ai_bias` domain lists core concepts, method keywords and context terms that are used by `search.query_builder` to generate systematic queries.  Influence score weights define how to combine PageRank, in‑degree, betweenness and citation counts into a single ranking.

## Usage

To access settings within code, import the `settings` singleton:

```python
from srp.config.settings import settings

api_key = settings.openalex_api_key
max_citations = settings.max_citations
```

CLI commands and web routes rely on `settings` for defaults.  You can override settings by creating a `.env` file in the project root or by passing environment variables when running the application.