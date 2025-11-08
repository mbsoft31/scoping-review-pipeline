# Core Module

The **core** module defines the fundamental data structures and helper functions used throughout the Systematic Review Pipeline.  It establishes common models for representing papers, authors and sources, and provides utilities for normalising identifiers and cleaning metadata.

## Contents

- **`models.py`** – Defines Pydantic models for bibliographic entities:
  - `Author`: Represents an author with first and last names and an optional ORCID.
  - `Source`: Captures provenance information about a retrieved paper, including the originating database, query string and retrieval timestamp.
  - `Paper`: The central record type representing a scholarly paper.  It contains fields such as `paper_id`, `doi`, `arxiv_id`, `title`, `abstract`, `authors`, publication year, venue, fields of study, citation counts and open‑access information.  The `source` field links back to the `Source` object.  The model uses validators to normalise DOIs and arXiv identifiers and to coerce publication years into integers.
  - `Reference`: Represents a citation reference with a DOI and optional year.  Used when enriching papers with citation data.
  - `DeduplicationCluster`: Groups together records that were identified as duplicates.  It records the canonical ID and the list of duplicate IDs.

- **`ids.py`** – Helper functions for working with identifiers:
  - `normalize_doi(doi: str) -> Optional[str]`: Lowercases and strips a DOI, returning `None` if it cannot be parsed.
  - `normalize_arxiv_id(arxiv_id: str) -> Optional[str]`: Normalises arXiv identifiers to the standard format (e.g. `1706.03762`).
  - `generate_paper_id(title: str, authors: List[Author], year: Optional[int]) -> str`: Creates a deterministic hash‑based identifier for a paper using its title, authors and year.  This function is used when papers lack a DOI or arXiv ID.
  - `compute_title_hash(title: str) -> str`: Computes a hash of a normalised title to assist with fuzzy matching during deduplication.

- **`normalization.py`** – Text cleaning utilities:
  - `normalize_title(title: str) -> str`: Lowercases and collapses whitespace in a title string.
  - `parse_date(date_str: str) -> Optional[datetime.date]`: Parses a date string in various formats (year, year‑month, full date) and returns a `date` object.
  - `extract_year(date_str: str) -> Optional[int]`: Extracts the year component from a date string.
  - `clean_abstract(abstract: str) -> str`: Removes newlines and collapses whitespace in an abstract.

## Usage

The core models are used by other modules to represent and pass around paper metadata.  For example, when the search module yields results from OpenAlex, each entry is converted into a `Paper` instance.  The deduplication module relies on the `paper_id` and DOI/arXiv normalisation functions to group duplicates.  Downstream modules such as screening, extraction and meta‑analysis use the same `Paper` objects.

Because the models are based on [Pydantic](https://docs.pydantic.dev/), they perform runtime type validation and offer convenient `model_dump()` methods for serialisation.  Optional fields may be omitted on input and will default to `None` or empty lists.