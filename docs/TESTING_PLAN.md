# Testing Plan: Dev to Production
## Systematic Review Pipeline - Core Modules

**Generated:** November 8, 2025  
**Version:** 1.0  
**Modules Covered:** Core, Search, Deduplication

---

## Executive Summary

This document outlines a comprehensive testing strategy to ensure the systematic review pipeline's core modules (Core, Search, Dedup) are production-ready. The plan follows a multi-layered testing approach combining unit tests, integration tests, performance tests, and end-to-end validation.

---

## 1. Module Overview

### 1.1 Core Module (`src/srp/core/`)
**Purpose:** Foundational data models and utilities

**Components:**
- `models.py` - Pydantic models (Paper, Author, Source, Reference, DeduplicationCluster)
- `ids.py` - ID normalization (DOI, arXiv, paper ID generation)
- `normalization.py` - Text/metadata normalization (titles, dates, abstracts)

**Critical Paths:**
- DOI/arXiv ID normalization consistency
- Model validation and serialization
- Date parsing robustness

---

### 1.2 Search Module (`src/srp/search/`)
**Purpose:** Multi-source academic search with caching and resumability

**Components:**
- `base.py` - Abstract SearchClient interface
- `orchestrator.py` - Multi-source search coordination
- `query_builder.py` - Systematic query generation
- `adapters/` - Source-specific implementations (OpenAlex, SemanticScholar, Crossref, arXiv)

**Critical Paths:**
- API rate limiting and retry logic
- Cursor/offset pagination correctness
- Cache consistency and resumability
- Multi-source orchestration

---

### 1.3 Dedup Module (`src/srp/dedup/`)
**Purpose:** Multi-strategy deduplication

**Components:**
- `deduplicator.py` - Three-pass deduplication (DOI → arXiv → fuzzy title)

**Critical Paths:**
- Exact match accuracy (DOI, arXiv)
- Fuzzy matching precision/recall balance
- Canonical selection logic
- Data merging completeness

---

## 2. Testing Pyramid

```
                    /\
                   /  \
                  / E2E \          ← End-to-End (5%)
                 /--------\
                /          \
               / Integration \     ← Integration (15%)
              /--------------\
             /                \
            /   Unit Tests     \   ← Unit Tests (80%)
           /____________________\
```

### Distribution
- **Unit Tests:** 80% (Fast, isolated, comprehensive coverage)
- **Integration Tests:** 15% (Module interactions, external deps)
- **E2E Tests:** 5% (Full pipeline validation)

---

## 3. Test Categories & Coverage

### 3.1 Unit Tests

#### 3.1.1 Core Module Tests
**File:** `tests/unit/test_core_models.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_paper_model_validation` | P0 | Valid Paper creation with all fields |
| `test_paper_minimal_fields` | P0 | Paper with only required fields |
| `test_paper_invalid_year` | P1 | Year outside 1900-2100 range |
| `test_doi_normalization_in_model` | P0 | DOI normalization via validator |
| `test_arxiv_normalization_in_model` | P0 | arXiv ID normalization via validator |
| `test_author_model` | P1 | Author with optional fields |
| `test_source_model` | P1 | Source tracking information |
| `test_dedup_cluster_model` | P1 | DeduplicationCluster validation |
| `test_paper_serialization` | P1 | JSON serialization/deserialization |
| `test_model_copy_deep` | P2 | Deep copy doesn't share references |

**File:** `tests/unit/test_core_ids.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_normalize_doi_standard` | P0 | Standard DOI formats |
| `test_normalize_doi_with_prefixes` | P0 | All URL/prefix variants |
| `test_normalize_doi_case_insensitive` | P0 | Uppercase to lowercase |
| `test_normalize_doi_edge_cases` | P1 | Empty, None, whitespace |
| `test_normalize_arxiv_versions` | P0 | Version stripping (v1, v2, etc.) |
| `test_normalize_arxiv_prefixes` | P0 | "arxiv:" prefix handling |
| `test_generate_paper_id` | P1 | Consistent ID generation |
| `test_compute_title_hash` | P0 | Deterministic hashing |
| `test_title_hash_normalization` | P0 | Case/punctuation invariance |

**File:** `tests/unit/test_core_normalization.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_normalize_title_basic` | P0 | Lowercase + punctuation removal |
| `test_normalize_title_whitespace` | P0 | Multiple spaces → single space |
| `test_parse_date_formats` | P0 | All supported date formats |
| `test_parse_date_invalid` | P1 | Graceful handling of bad dates |
| `test_extract_year` | P1 | Year extraction from date |
| `test_clean_abstract_length` | P1 | Truncation at max_length |
| `test_clean_abstract_whitespace` | P1 | Whitespace normalization |

---

#### 3.1.2 Search Module Tests
**File:** `tests/unit/test_search_query_builder.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_generate_core_pairs` | P0 | Combinatorial query generation |
| `test_generate_augmented_queries` | P0 | Method/context augmentation |
| `test_optimize_for_semantic_scholar` | P1 | Source-specific optimization |
| `test_systematic_queries_generation` | P0 | Full query set generation |
| `test_query_deduplication` | P1 | No duplicate queries |
| `test_save_queries` | P2 | Query persistence |

**File:** `tests/unit/test_search_cache.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_cache_initialization` | P0 | Schema creation |
| `test_register_query` | P0 | Query registration |
| `test_compute_query_id_deterministic` | P0 | Same inputs → same ID |
| `test_cache_paper` | P0 | Paper storage |
| `test_get_cached_papers` | P0 | Paper retrieval |
| `test_mark_completed` | P1 | Completion tracking |
| `test_get_query_progress` | P1 | Progress retrieval |
| `test_cache_concurrency` | P2 | Thread-safe operations |

**File:** `tests/unit/test_search_base.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_search_client_interface` | P0 | Abstract class enforcement |
| `test_client_source_name` | P1 | Source name extraction |

---

#### 3.1.3 Dedup Module Tests
**File:** `tests/unit/test_dedup_deduplicator.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_deduplicate_exact_doi` | P0 | DOI-based deduplication |
| `test_deduplicate_doi_normalization` | P0 | DOI prefix variants |
| `test_deduplicate_exact_arxiv` | P0 | arXiv-based deduplication |
| `test_deduplicate_fuzzy_title` | P0 | Title similarity matching |
| `test_fuzzy_threshold_boundary` | P1 | Threshold edge cases |
| `test_no_duplicates` | P1 | No false positives |
| `test_select_canonical_citations` | P0 | Most-cited selection |
| `test_select_canonical_completeness` | P0 | Best-completeness selection |
| `test_merge_paper_data` | P0 | Field merging logic |
| `test_merge_external_ids` | P1 | External ID consolidation |
| `test_merge_open_access` | P1 | OA PDF preservation |
| `test_cluster_confidence` | P1 | Confidence scoring |
| `test_get_canonical_id` | P1 | ID mapping retrieval |

---

### 3.2 Integration Tests

#### 3.2.1 Search Integration
**File:** `tests/integration/test_search_adapters.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_openalex_search_basic` | P0 | Live OpenAlex API call |
| `test_openalex_pagination` | P1 | Cursor pagination |
| `test_openalex_rate_limiting` | P1 | Rate limiter behavior |
| `test_semantic_scholar_search` | P1 | Live S2 API call |
| `test_crossref_search` | P2 | Live Crossref API call |
| `test_arxiv_search` | P2 | Live arXiv API call |
| `test_search_with_date_filters` | P1 | Date range filtering |

**File:** `tests/integration/test_search_orchestrator.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_orchestrator_single_source` | P0 | Single source coordination |
| `test_orchestrator_multi_source` | P0 | Multi-source parallel search |
| `test_orchestrator_with_cache` | P0 | Cache hit/miss behavior |
| `test_orchestrator_resume` | P0 | Resume from cached state |
| `test_orchestrator_error_handling` | P1 | Graceful source failures |

#### 3.2.2 Core-Dedup Integration
**File:** `tests/integration/test_core_dedup_integration.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_dedup_with_real_papers` | P0 | Dedup on actual paper data |
| `test_dedup_preserves_model_validity` | P0 | Output papers validate |
| `test_dedup_cluster_referential_integrity` | P1 | Cluster IDs exist in papers |

---

### 3.3 Performance Tests

**File:** `tests/performance/test_dedup_performance.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_dedup_1k_papers` | P0 | 1,000 papers < 5s |
| `test_dedup_10k_papers` | P1 | 10,000 papers < 60s |
| `test_dedup_memory_usage` | P2 | Memory profiling |

**File:** `tests/performance/test_search_cache_performance.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_cache_write_throughput` | P1 | Bulk paper caching |
| `test_cache_read_latency` | P1 | Retrieval performance |

---

### 3.4 End-to-End Tests

**File:** `tests/e2e/test_search_dedup_pipeline.py`

| Test Case | Priority | Description |
|-----------|----------|-------------|
| `test_full_search_dedup_workflow` | P0 | Search → Cache → Dedup |
| `test_multi_source_dedup` | P0 | Multiple sources → unified dedup |
| `test_pipeline_idempotency` | P1 | Re-run produces same results |

---

## 4. Test Data Strategy

### 4.1 Fixtures
**Location:** `tests/fixtures/`

- `sample_papers.json` - 50 diverse Paper objects
- `duplicate_papers.json` - Known duplicate sets
- `api_responses/` - Mocked API responses
  - `openalex_response.json`
  - `semantic_scholar_response.json`
  - `crossref_response.json`
  - `arxiv_response.json`

### 4.2 Factory Pattern
```python
# tests/factories.py
class PaperFactory:
    @staticmethod
    def create(**kwargs) -> Paper:
        # Generate realistic test papers
```

---

## 5. Mocking Strategy

### External Dependencies to Mock
1. **HTTP Clients** - Use `respx` for httpx mocking
2. **File I/O** - Use `tmp_path` fixtures
3. **Database** - In-memory SQLite for cache tests
4. **Rate Limiters** - Mock time.sleep() for speed

### Example Mock Structure
```python
import respx
from httpx import Response

@respx.mock
async def test_openalex_search():
    respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json={...})
    )
```

---

## 6. Coverage Targets

### Minimum Coverage Requirements
- **Core Module:** 95% line coverage
- **Search Module:** 85% line coverage (excluding network I/O)
- **Dedup Module:** 95% line coverage

### Coverage Exclusions
- `__init__.py` files
- Abstract base classes (already tested via implementations)
- Logging statements

---

## 7. CI/CD Integration

### GitHub Actions Workflow
```yaml
name: Test Pipeline

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-cov pytest-asyncio respx
      
      - name: Run unit tests
        run: pytest tests/unit -v --cov=src/srp --cov-report=xml
      
      - name: Run integration tests
        run: pytest tests/integration -v
        env:
          OPENALEX_EMAIL: ${{ secrets.OPENALEX_EMAIL }}
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 8. Test Execution Plan

### Phase 1: Unit Tests (Week 1)
- [ ] Implement all P0 unit tests
- [ ] Achieve 80% coverage on Core
- [ ] Achieve 70% coverage on Search
- [ ] Achieve 85% coverage on Dedup

### Phase 2: Integration Tests (Week 2)
- [ ] Implement search adapter integration tests
- [ ] Implement orchestrator tests
- [ ] Mock external APIs properly
- [ ] Test cache resumability

### Phase 3: Performance & E2E (Week 3)
- [ ] Benchmark deduplication at scale
- [ ] Full pipeline validation
- [ ] Load testing (if applicable)
- [ ] Documentation updates

### Phase 4: Production Readiness (Week 4)
- [ ] All P0 and P1 tests passing
- [ ] Coverage targets met
- [ ] CI/CD pipeline established
- [ ] Monitoring/alerting configured
- [ ] Performance baselines documented

---

## 9. Quality Gates

### Pre-Production Checklist
- [ ] **Code Coverage:** ≥90% overall, ≥85% per module
- [ ] **Test Pass Rate:** 100% of P0 tests, ≥95% of P1 tests
- [ ] **Performance:** No regressions from baseline
- [ ] **Documentation:** All public APIs documented
- [ ] **Security:** No secrets in code, API keys properly managed
- [ ] **Linting:** Black, isort, mypy all passing
- [ ] **Type Hints:** 100% type coverage in core modules
- [ ] **Error Handling:** All exceptions properly caught/logged

---

## 10. Tools & Dependencies

### Testing Tools
```txt
# requirements-dev.txt
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0
pytest-timeout>=2.2.0
respx>=0.20.0
faker>=20.0.0
hypothesis>=6.92.0  # Property-based testing
```

### Code Quality Tools
```txt
black>=23.12.0
isort>=5.13.0
mypy>=1.7.0
ruff>=0.1.9
```

---

## 11. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| API rate limits in tests | Medium | Mock all external calls in unit tests |
| Flaky async tests | High | Use proper fixtures, increase timeouts |
| Test data staleness | Medium | Automated fixture regeneration |
| Coverage blind spots | High | Branch coverage + mutation testing |
| Integration test cost | Low | Run on PRs only, not every commit |

---

## 12. Success Metrics

### Quantitative
- **Test Execution Time:** Unit tests < 10s, Integration < 2min
- **Defect Escape Rate:** < 1 bug per 1000 LOC in production
- **Test Maintenance Burden:** < 20% of dev time

### Qualitative
- **Developer Confidence:** Team comfortable deploying
- **Debugging Efficiency:** Failures point to root cause
- **Regression Prevention:** No recurring bugs

---

## 13. Continuous Improvement

### Post-Production
1. **Monitor Test Flakiness:** Track and fix flaky tests
2. **Performance Regression Testing:** Automate benchmarking
3. **Mutation Testing:** Validate test quality with `mutmut`
4. **Property-Based Testing:** Add Hypothesis tests for edge cases
5. **User Feedback Loop:** Bug reports → new test cases

---

## Appendix A: Example Test Implementation

See `tests/unit/test_core_ids.py` for reference implementation following this plan.

---

## Appendix B: Resources
- [Pytest Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)
- [Testing Async Code](https://pytest-asyncio.readthedocs.io/)
- [Pydantic Testing](https://docs.pydantic.dev/latest/concepts/serialization/)

---

**Document Status:** ✅ Ready for Implementation  
**Next Review:** After Phase 1 completion

