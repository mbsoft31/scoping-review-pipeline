# Quick Start Guide - Scoping Review Pipeline

Get up and running in 5 minutes!

## Step 1: Installation

```
git clone https://github.com/mbsoft31/scoping-review-pipeline.git
cd scoping-review-pipeline
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2: Configuration

Create `.env` file:

```
# Optional but recommended for better rate limits
OPENALEX_EMAIL=your.email@university.edu
SEMANTIC_SCHOLAR_API_KEY=your_s2_api_key_here

# Cache and output directories
CACHE_DIR=.cache
OUTPUT_DIR=output
```

## Step 3: Run Your First Search

```
from srp.async_queue import SearchQueueManager

# Create manager with 3 workers
manager = SearchQueueManager(num_workers=3)

# Add a search
task_id = manager.add_search(
    source="openalex",
    query="machine learning fairness",
    limit=100
)

# Run all queued searches
manager.run_all()

# Get results
papers = manager.get_results(task_id)
print(f"Found {len(papers)} papers!")

# Print first paper
if papers:
    p = papers[0]
    print(f"Title: {p.title}")
    print(f"Authors: {', '.join(a.name for a in p.authors[:3])}")
    print(f"Year: {p.year}")
```

## Step 4: Run Tests

```
pytest tests/queue/
```

## Step 5: Enable Metrics (Optional)

```
from srp.async_queue.metrics import MetricsCollector

collector = MetricsCollector()
# Use collector with your searches
# ...
collector.export_prometheus()  # → .metrics/metrics.prom
```

## Next Steps

- Read the full documentation: `docs/`
- Check examples: `examples/queue/`
- See advanced features: `docs/ADVANCED.md`

## Troubleshooting

**Rate limit errors from Semantic Scholar?**
- Add your API key to `.env`
- Reduce `num_workers` to 1-2

**Network timeout errors?**
- Check internet connection
- Increase timeout in adapter config

**Need help?**
- Open an issue: https://github.com/mbsoft31/scoping-review-pipeline/issues
