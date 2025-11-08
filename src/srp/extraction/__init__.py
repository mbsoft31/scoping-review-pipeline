"""Extraction package for automatically retrieving and extracting data from full‑text articles.

This package contains utilities to download full texts (via open access
links or Unpaywall), parse PDF content into text and detect sections,
and extract structured information such as sample sizes, effect sizes,
p‑values and statistical methods.  The extraction step forms the
foundation of downstream quality assessment and meta‑analysis
workflows.

Modules:

  extractor: Implements the ``DataExtractor`` class and supporting
      structures for parsing full‑text documents and extracting
      structured results.
  models: Pydantic models representing the structured outputs of
      extraction, including interventions, outcomes and quality
      indicators.

"""

from .models import ExtractedData, Intervention, Outcome, StudyDesignType  # noqa: F401
from .extractor import DataExtractor, FullTextRetriever, FullTextDocument  # noqa: F401