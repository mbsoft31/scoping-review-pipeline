import pytest
from srp.async_queue.batch import BatchProcessor

@pytest.mark.skipif(
    not (hasattr(BatchProcessor, "search_multiple_queries")),
    reason="BatchProcessor or methods not available."
)
def test_batch_processor_smoke(tmp_path):
    batch = BatchProcessor(num_workers=1, cache_dir=tmp_path)
    results = batch.search_multiple_queries(
        source="openalex",
        queries=["cancer", "diabetes"],
        limit=2,
    )
    assert isinstance(results, list) and len(results) > 0
