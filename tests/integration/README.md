"""
Integration Testing Suite - Systematic Review Pipeline
========================================================

This suite contains comprehensive integration tests that verify modules
work correctly together across the entire pipeline.

Test Organization
-----------------

1. test_search_to_dedup.py
   - Tests Search → Deduplication flow
   - Multi-source search integration
   - Duplicate detection across sources
   - Data preservation through dedup

2. test_dedup_to_enrich.py
   - Tests Deduplication → Enrichment flow
   - Citation enrichment from multiple sources
   - Influence score computation
   - Reference resolution

3. test_full_pipeline.py
   - Complete end-to-end pipeline tests
   - Search → Dedup → Enrich → Export
   - Multi-format output testing
   - Resume capability testing
   - Error recovery scenarios

4. test_io_persistence.py
   - I/O operations and data persistence
   - File format conversions (Parquet, CSV, BibTeX)
   - Cache functionality
   - Data validation
   - Large dataset handling

5. test_end_to_end.py (existing)
   - Legacy end-to-end tests
   - Phase-based workflow testing

6. test_web_api.py (existing)
   - Web API integration tests
   - FastAPI endpoint testing
   - API request/response validation


Running the Tests
-----------------

Run all integration tests:
    pytest tests/integration/ -v

Run with coverage:
    pytest tests/integration/ -v --cov=src/srp --cov-report=html

Run specific test file:
    pytest tests/integration/test_search_to_dedup.py -v

Run specific test:
    pytest tests/integration/test_full_pipeline.py::test_full_pipeline_search_to_influence -v

Run only fast tests (skip slow/API-dependent tests):
    pytest tests/integration/ -v -m "not slow"

Run tests in parallel (requires pytest-xdist):
    pytest tests/integration/ -v -n auto


Test Markers
------------

- @pytest.mark.integration: All integration tests
- @pytest.mark.asyncio: Async tests (API calls)
- @pytest.mark.slow: Slow-running tests (full API queries)
- @pytest.mark.e2e: Complete end-to-end tests


Environment Requirements
------------------------

Integration tests require:
- Network access (for external API calls)
- Sufficient disk space (for temporary files)
- API keys may be needed for some sources (set in .env or environment)

Some tests will skip or xfail if:
- Network is unavailable
- API rate limits are hit
- External services are down


Expected Outcomes
-----------------

✓ All modules integrate correctly
✓ Data flows properly between pipeline stages
✓ File I/O operations work across formats
✓ Caching and resume functionality works
✓ Error handling is robust
✓ Multi-source searches combine correctly
✓ Deduplication removes duplicates across sources
✓ Citation enrichment adds reference data
✓ Influence scores are computed correctly
✓ Export formats are valid


Troubleshooting
---------------

If tests fail:

1. Network Issues
   - Check internet connection
   - Verify API endpoints are accessible
   - Check for rate limiting

2. Disk Space
   - Ensure temp directory has sufficient space
   - Tests create and clean up temporary files

3. API Keys
   - Some sources may require authentication
   - Set environment variables as needed

4. Timeouts
   - Increase timeout values for slow networks
   - Use smaller limits in tests if needed

5. Data Validation
   - Check that output files are created
   - Verify file formats are correct
   - Ensure data integrity across stages


Performance Notes
-----------------

- Fast tests: <1 second (mocked/sample data)
- Medium tests: 1-10 seconds (small API calls)
- Slow tests: >10 seconds (full searches, large datasets)

Use markers to control which tests run in CI/CD vs local development.


Coverage Goals
--------------

Integration tests should cover:
- ✓ Module interactions (90%+ coverage)
- ✓ Data flow between stages (100% coverage)
- ✓ Error propagation (80%+ coverage)
- ✓ I/O operations (95%+ coverage)
- ✓ Caching mechanisms (90%+ coverage)


Next Steps
----------

After integration testing:
1. Frontend/UI testing (React components)
2. Performance benchmarking
3. Load testing for concurrent users
4. Security testing (input validation, injection)
5. User acceptance testing (UAT)
"""

