# I/O Module

The **io** module contains utilities for reading from and writing to disk, caching results and exporting bibliographies.  These helpers are used throughout the pipeline to persist intermediate data and produce human‑readable outputs.

## Cache

[`cache.py`](../../src/srp/io/cache.py) implements `SearchCache`, an SQLite‑backed cache that supports resumable searches.  Key features include:

- Registering queries and pages: `register_query()` assigns a unique ID to each query and stores configuration metadata.  `cache_page()` stores raw page responses keyed by query ID and page index.
- Storing and retrieving papers: `cache_papers()` saves parsed `Paper` objects to the database.  `get_papers_for_query()` retrieves cached papers for a given query.
- Marking a query as completed: `set_query_completed()` signals that all pages for a query have been processed.

The cache uses WAL mode and performance‑oriented pragmas to improve write speeds.  When resume mode is enabled, the orchestrator checks the cache before making new HTTP requests.

## Paths

[`paths.py`](../../src/srp/io/paths.py) defines helper functions:

- `create_output_dir(prefix: str) -> Path`: Creates a timestamped output directory under the `output_dir` configured in `settings`.  Returns the new path.
- `get_cache_path(name: str) -> Path`: Returns the path to the cache file for a given name under `cache_dir`.

## BibTeX Export

[`bibtex.py`](../../src/srp/io/bibtex.py) provides the `BibTeXExporter` class.  It can take a list of `Paper` objects and write a `.bib` file.  The exporter:

- Sanitises strings (e.g. escaping special characters).
- Formats author names as “Last, First”.
- Generates citation keys using the first author’s last name, publication year and first word of the title.
- Includes fields such as title, abstract, year, venue and DOI.

## Validation

[`validation.py`](../../src/srp/io/validation.py) defines `DataValidator`, which inspects intermediate outputs for common issues:

- Schema compliance – ensures required fields are present.
- Identifier patterns – checks DOI and arXiv ID formats.
- Publication dates – warns about missing or future dates.
- Completeness – flags records lacking titles or abstracts.
- Duplicate identifiers – warns if duplicate DOIs or arXiv IDs remain after deduplication.
- Citation integrity – verifies that citation edges refer to known paper IDs.

The `validate_phase_output()` function orchestrates these checks for a phase directory and prints a report.  The CLI exposes a `validate` command to run these checks.