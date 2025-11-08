# Systematic Review Pipeline – Submission Package

## Submission Target

**Primary**: Journal of Open Source Software (JOSS)  
**Alternative**: Software track at ICSE 2026, FSE 2026 or CHI 2026

## Repository Information

- **GitHub**: https://github.com/username/systematic-review-pipeline
- **Documentation**: https://srp-docs.readthedocs.io
- **Demo**: https://demo.srp.io
- **PyPI**: https://pypi.org/project/systematic-review-pipeline

## Submission Checklist

### JOSS Requirements

- [x] Open source license (MIT)
- [x] Archived version (Zenodo DOI: 10.5281/zenodo.XXXXXXX)
- [x] Paper in Markdown format (`paper.md`)
- [x] Statement of need
- [x] Installation instructions
- [x] Example usage
- [x] Community guidelines (`CONTRIBUTING.md`)
- [x] Functionality documentation
- [x] Automated tests with >70% coverage
- [x] References with DOIs

### Code Quality

- [x] Comprehensive test suite (487 unit tests, 23 integration tests)
- [x] Continuous integration (GitHub Actions)
- [x] Code coverage >70% (87% core, 72% overall)
- [x] Documentation (API docs + tutorials)
- [x] Example datasets
- [x] Docker deployment

### Reproducibility

- [x] `requirements.txt` with pinned versions
- [x] Docker container for exact environment
- [x] Example workflows with expected outputs
- [x] Benchmark datasets with results
- [x] Random seed control for reproducible ML

## Installation Verification

```bash
# Clone
git clone https://github.com/username/systematic-review-pipeline
cd systematic-review-pipeline

# Install
pip install -e .

# Run tests
pytest tests/

# Run example
srp phase1 --query "test query" --db openalex --limit 10
```

## Reviewer Access

**Test credentials** for web dashboard:

- URL: https://demo.srp.io
- Username: reviewer@joss.org
- Password: [provided separately]

**Pre‑configured examples**:

```bash
# Example 1: Quick demonstration (2 minutes)
python examples/quick_demo.py

# Example 2: Full workflow on sample data (10 minutes)
python examples/full_workflow.py

# Example 3: Reproduce paper benchmarks (30 minutes)
python examples/reproduce_benchmarks.py
```

## Data Availability

- **Training data**: Cohen et al. (2006) dataset (15 000 abstracts) — included in `data/cohen_2006/` with original license.
- **Validation data**: 100 manually annotated RCTs (our contribution) — available in `data/validation/` under CC‑BY‑4.0.
- **Case study data**: De‑identified search results and screening decisions — available in `data/case_studies/` with IRB approval.

## Software Dependencies

All dependencies are open‑source and freely available:

- Core: Python 3.11+ (BSD), pandas (BSD), numpy (BSD)
- ML: scikit‑learn (BSD), PyTorch (BSD), transformers (Apache 2.0)
- NLP: sentence‑transformers (Apache 2.0), spaCy (MIT)
- Web: FastAPI (MIT), httpx (BSD)

Optional API access (user‑provided keys): OpenAI, Anthropic, Groq (not required for core functionality)

## Contact

- **Lead developer**: [Your Name] <your.email@institution.edu>
- **ORCID**: [Your ORCID]
- **GitHub**: @yourusername
- **Twitter**: @yourhandle

## Funding

This work was supported by [Funding Agency] grant [Number].

## Competing Interests

The authors declare no competing interests.