# Extraction Module

The **extraction** module implements automated data extraction from the full texts of research papers.  Its goal is to turn unstructured article content into structured data suitable for synthesis and meta‑analysis.

## Models

[`models.py`](../../src/srp/extraction/models.py) defines Pydantic models representing extracted information:

- `StudyDesignType`: An enum of study types (e.g. randomised controlled trial, cohort study, case‑control, cross‑sectional, systematic review).  Used to categorise study design.
- `Intervention`: Describes an intervention or exposure, including name, dosage, duration and optional description.
- `Outcome`: Represents an outcome measure with a name, measurement description, time point, effect size and statistics.
- `ExtractedData`: The main container for extracted data.  It includes the paper ID, study design, sample size, population and setting descriptors, lists of interventions and outcomes, lists of p‑values and effect sizes, statistical methods mentioned, quality indicators (e.g. control group, randomisation, blinding), and metadata such as extraction timestamp and confidence score.

## DataExtractor

Implemented in [`extractor.py`](../../src/srp/extraction/extractor.py), the `DataExtractor` class provides heuristics for pulling out structured information from the methods and results sections of a full‑text document.  Its responsibilities include:

- **Pattern matching** – Uses regular expressions to locate sample sizes, p‑values, effect sizes (e.g. odds ratios, relative risks, hazard ratios, Cohen’s d) and confidence intervals.
- **Study design detection** – Searches for keywords indicative of specific study designs (e.g. “randomised”, “cohort”, “case‑control”) and returns the most likely design type.
- **Statistical methods extraction** – Looks for mentions of common statistical techniques (t‑tests, ANOVA, regression, chi‑square tests, meta‑analysis, mixed models) in the methods section.
- **Section aggregation** – Accepts a `FullTextDocument` (containing a mapping of section names to text) and combines the relevant sections (abstract, methods, results) for processing.
- **NER placeholders** – The extractor stubs out named‑entity recognition for interventions and outcomes.  These would require integration with an NLP library (e.g. spaCy or transformers) to identify domain‑specific entities.

### Usage

```python
from srp.extraction.extractor import DataExtractor, FullTextDocument

extractor = DataExtractor()
doc = FullTextDocument(
    paper_id="P123",
    text=full_text,
    sections={"abstract": abstract, "methods": methods, "results": results},
    source="pdf",
)

extracted = extractor.extract_from_sections(doc)
print(extracted.study_design)
print(extracted.sample_size)
print(extracted.effect_sizes)
```

The `FullTextRetriever` class (also in `extractor.py`) supports downloading PDFs or using the Unpaywall API to retrieve open‑access versions.  PDF parsing into text is not yet implemented (left as a placeholder), but you can integrate tools such as [PyMuPDF](https://pymupdf.readthedocs.io/) or [pdfplumber](https://pypi.org/project/pdfplumber/) to extract text before passing it to the extractor.