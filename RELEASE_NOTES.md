# Release Notes - Scoping Review Pipeline v1.0.0

## 🎉 First Production-Ready Release

**Release Date:** November 9, 2025  
**Status:** Battle-Tested & Production-Ready

---

## 🚀 Major Features

### Async Task Queue System
- **Priority-based task scheduling** with persistent state
- **Worker pool** with configurable concurrency (1-10 workers)
- **Automatic retry** with intelligent backoff strategies
- **Resume capability** from cache after interruptions
- **Real-time progress tracking** with Rich terminal UI

### Multi-Source Search Integration
- ✅ **OpenAlex** (10 req/s, burst=15)
- ✅ **Semantic Scholar** (1 req/s, burst=3) - 5x performance improvement
- ✅ **arXiv** (0.33 req/s, burst=1)
- ✅ **Crossref** (50 req/s, burst=100)

### Intelligent Error Handling
- **Circuit breaker pattern** to prevent cascading failures
- **Error classification** (rate limit, network, API, parse errors)
- **Adaptive backoff** with jitter to prevent thundering herd
- **Per-service circuit breakers** for isolated fault tolerance

### Batch Processing
- Search multiple queries across one source
- Search one query across multiple sources
- Automatic deduplication by DOI and title
- Convenience functions for common workflows

---

## 🔧 Critical Fixes

### Semantic Scholar Adapter (5x Performance Boost)
**Before:**
- Rate: 0.25 req/s
- Per-page delay: 1.3s
- Total: ~5.3s per page

**After:**
- Rate: 1.0 req/s (4x increase)
- Burst: 3 requests
- Per-page delay: removed
- **Total: ~1.0s per page (5x faster!)**

### Additional Improvements
- Fixed API key header handling (no more quote stripping issues)
- Improved 429 error handling with token reset
- Better error messages and logging

---

## 📊 Metrics & Monitoring

### Prometheus Integration
- Automatic metric collection for all queue operations
- Export formats: Prometheus, JSON, CSV
- Pre-built Grafana dashboard included

### Key Metrics
- `srp_queue_total_tasks` - Total tasks processed
- `srp_queue_papers_per_minute` - Throughput
- `srp_papers_by_source{source}` - Per-source statistics
- `srp_errors_by_type{error_type}` - Error distribution

---

## 🧪 Testing & Quality

### Test Coverage
- ✅ Unit tests for task queue
- ✅ Worker pool and concurrency tests
- ✅ Error handler and circuit breaker tests
- ✅ Integration tests for batch processing
- ✅ End-to-end workflow validation

### Battle-Tested Scenarios
- Network failures and timeouts
- API rate limiting (429 responses)
- Circuit breaker state transitions
- Task interruption and resume
- Concurrent worker execution

---

## 📚 Usage Examples

### Basic Queue Usage
```
from srp.async_queue import SearchQueueManager

manager = SearchQueueManager(num_workers=3)

# Add searches
manager.add_search("openalex", "machine learning fairness", limit=500)
manager.add_search("arxiv", "neural networks", limit=200)

# Run (blocking until done)
manager.run_all()

# Get results
results = manager.get_all_results()
print(f"Total papers: {sum(len(p) for p in results.values())}")
```

### Batch Processing
```
from srp.async_queue.batch import search_multiple_queries

papers = search_multiple_queries(
    source="openalex",
    queries=["AI fairness", "ML bias", "algorithmic equity"],
    limit=500,
    num_workers=5
)
```

### With Metrics
```
from srp.async_queue.metrics import MetricsCollector

collector = MetricsCollector()
manager = SearchQueueManager(num_workers=3, metrics_collector=collector)

# ... run searches ...

# Export metrics
collector.export_prometheus()
collector.export_json()
print(collector.get_summary())
```

---

## 🔄 Migration Guide

### From v0.x to v1.0

**Breaking Changes:**
- None! Fully backward compatible.

**Deprecated (will be removed in v2.0):**
- `settings.semantic_scholar_rate_limit` - Use `adapter_config.py` instead
- `settings.openalex_rate_limit` - Use `adapter_config.py` instead

**Recommended Updates:**
1. Update `.env` file with API keys if not already set
2. Review new adapter configurations in `src/srp/config/adapter_config.py`
3. Enable metrics collection for production deployments

---

## 📦 Installation

```
git clone https://github.com/mbsoft31/scoping-review-pipeline.git
cd scoping-review-pipeline
pip install -r requirements.txt
```

### Optional Dependencies
```
pip install prometheus-client  # For Prometheus metrics
```

---

## 🐛 Known Issues

None at this time.

---

## 🙏 Acknowledgments

- OpenAlex team for excellent API documentation
- Semantic Scholar for academic search capabilities
- Python asyncio community for patterns and best practices

---

## 📞 Support

- **Issues:** https://github.com/mbsoft31/scoping-review-pipeline/issues
- **Discussions:** https://github.com/mbsoft31/scoping-review-pipeline/discussions
- **Email:** bekhouche.mouadh@univ-oeb.dz

---

## 📄 License

This project is licensed under the MIT License.

---

## 🎯 Roadmap for v1.1

- [ ] CLI commands for queue management
- [ ] Daemon mode for background processing
- [ ] Connection pooling for HTTP clients
- [ ] Advanced deduplication with fuzzy matching
- [ ] Web dashboard for real-time monitoring
