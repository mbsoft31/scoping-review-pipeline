# Async Task Queue System

## Overview

The async queue system provides a simple way to manage concurrent searches without needing to understand async/await. It handles:

- **Priority-based execution**: Control which searches run first
- **Automatic retry**: Failed searches retry automatically
- **Cache integration**: Resume from cache if interrupted
- **Progress tracking**: Real-time progress with ETA
- **Concurrent execution**: Run multiple searches in parallel
- **Persistence**: Survives crashes - just restart and it continues

## Quick Start

```python
from srp.async_queue import SearchQueueManager

# Create manager
manager = SearchQueueManager(num_workers=3)

# Add searches
task1 = manager.add_search("openalex", "machine learning", limit=100)
task2 = manager.add_search("arxiv", "neural networks", limit=50)

# Run (blocks until done)
manager.run_all()

# Get results
papers1 = manager.get_results(task1)
papers2 = manager.get_results(task2)

print(f"OpenAlex: {len(papers1)} papers")
print(f"arXiv: {len(papers2)} papers")
```

## Key Concepts

### Workers

Workers execute tasks concurrently. More workers = faster execution but more API load.

**Recommended worker counts:**
- **2-3 workers**: Safe default, respects rate limits
- **4-5 workers**: Faster, but may hit rate limits
- **6+ workers**: Only if you have API keys and high rate limits

### Priority

Lower priority number = executes first.

```python
# High priority (runs first)
task1 = manager.add_search("openalex", "important query", priority=0)

# Low priority (runs later)
task2 = manager.add_search("arxiv", "less urgent", priority=10)
```

### Cache & Resume

Searches automatically cache results. If interrupted:

```python
# First run (partial completion before crash)
manager.add_search("openalex", "large query", limit=10000)
manager.run_all()  # Crashes at 5000 papers

# Second run (resumes from 5000)
manager.add_search("openalex", "large query", limit=10000)  # Same query!
manager.run_all()  # Continues from 5000, fetches remaining 5000
```

To disable cache:

```python
manager.add_search("openalex", "query", resume_from_cache=False)
```

## API Reference

### SearchQueueManager

#### `__init__(num_workers=3, cache_dir=None, strategy=None)`

Initialize the manager.

**Parameters:**
- `num_workers` (int): Number of concurrent workers (default: 3)
- `cache_dir` (Path): Cache directory (default: `.cache`)
- `strategy` (SearchStrategy): Search strategy (default: default strategy)

#### `add_search(source, query, **kwargs) -> str`

Add a search task.

**Parameters:**
- `source` (str): Database ("openalex", "arxiv", "crossref", "semantic_scholar")
- `query` (str): Search query
- `start_date` (date): Filter from date
- `end_date` (date): Filter until date
- `limit` (int): Max papers
- `priority` (int): Priority (0=highest)
- `config` (dict): Source-specific config
- `resume_from_cache` (bool): Resume from cache

**Returns:** task_id (str)

#### `add_multiple_searches(searches) -> List[str]`

Add multiple searches at once.

**Parameters:**
- `searches` (List[dict]): List of search configs

**Returns:** List of task_ids

#### `run_all(show_progress=True, progress_interval=2.0)`

Run all queued searches (blocking).

**Parameters:**
- `show_progress` (bool): Show live progress
- `progress_interval` (float): Update interval in seconds

#### `get_results(task_id) -> Optional[List[Paper]]`

Get results for a completed task.

**Parameters:**
- `task_id` (str): Task ID from add_search()

**Returns:** List of Paper objects or None

#### `get_all_results() -> Dict[str, List[Paper]]`

Get results from all completed tasks.

**Returns:** Dict mapping task_id -> papers

#### `get_task_status(task_id) -> Optional[str]`

Get current task status.

**Returns:** Status string or None

#### `cancel_task(task_id)`

Cancel a task.

#### `get_queue_size() -> int`

Get number of pending tasks.

## Usage Patterns

See [examples/queue_usage_examples.py](../../examples/queue_usage_examples.py) for complete examples.

### Pattern 1: Basic Sequential

```python
manager = SearchQueueManager(num_workers=3)

# Add searches
task1 = manager.add_search("openalex", "AI", limit=100)
task2 = manager.add_search("arxiv", "ML", limit=50)

# Run
manager.run_all()

# Get results
papers1 = manager.get_results(task1)
papers2 = manager.get_results(task2)
```

### Pattern 2: Batch with Priority

```python
manager = SearchQueueManager(num_workers=5)

searches = [
    {"source": "openalex", "query": "urgent query", "priority": 0},
    {"source": "openalex", "query": "normal query", "priority": 5},
    {"source": "arxiv", "query": "low priority", "priority": 10},
]

task_ids = manager.add_multiple_searches(searches)
manager.run_all()

for task_id in task_ids:
    papers = manager.get_results(task_id)
    print(f"Task {task_id[:8]}: {len(papers)} papers")
```

### Pattern 3: Date Filtering

```python
from datetime import date

manager = SearchQueueManager()

task_id = manager.add_search(
    source="openalex",
    query="climate change",
    start_date=date(2020, 1, 1),
    end_date=date(2024, 12, 31),
    limit=1000
)

manager.run_all()
papers = manager.get_results(task_id)
```

### Pattern 4: Context Manager

```python
# Automatic cleanup
with SearchQueueManager(num_workers=3) as manager:
    manager.add_search("openalex", "AI", limit=100)
    manager.add_search("arxiv", "ML", limit=50)
    manager.run_all()
    
    results = manager.get_all_results()
    total = sum(len(p) for p in results.values())
    print(f"Total: {total} papers")

# Cache automatically closed
```

### Pattern 5: Monitor and Cancel

```python
manager = SearchQueueManager(num_workers=3)

# Add many searches
task1 = manager.add_search("openalex", "AI", limit=5000)
task2 = manager.add_search("openalex", "ML", limit=5000)
task3 = manager.add_search("arxiv", "DL", limit=5000)

print(f"Queue size: {manager.get_queue_size()}")  # 3

# Cancel one
manager.cancel_task(task3)
print(f"Queue size: {manager.get_queue_size()}")  # 2

# Run remaining
manager.run_all()
```

## Best Practices

### 1. Use Appropriate Worker Count

```python
# Good: Respects rate limits
manager = SearchQueueManager(num_workers=3)

# Bad: May overwhelm APIs
manager = SearchQueueManager(num_workers=20)
```

### 2. Set Priorities Wisely

```python
# Important searches first
manager.add_search("openalex", "primary research", priority=0)
manager.add_search("openalex", "secondary research", priority=5)
manager.add_search("arxiv", "preprints", priority=10)
```

### 3. Use Limits for Testing

```python
# Test with small limit first
manager.add_search("openalex", "broad query", limit=10)
manager.run_all()

# If good, run full search
manager.add_search("openalex", "broad query", limit=5000)
manager.run_all()
```

### 4. Batch Related Searches

```python
# More efficient than individual add_search() calls
searches = [
    {"source": "openalex", "query": "ML fairness", "limit": 500},
    {"source": "openalex", "query": "ML bias", "limit": 500},
    {"source": "openalex", "query": "ML ethics", "limit": 500},
]
manager.add_multiple_searches(searches)
```

### 5. Handle Results Immediately

```python
# Good: Process results right after completion
manager.run_all()
for task_id, papers in manager.get_all_results().items():
    # Save to file, deduplicate, etc.
    save_papers(papers, f"results_{task_id}.csv")

# Bad: Keeping all results in memory
all_papers = []
for task_id in task_ids:
    all_papers.extend(manager.get_results(task_id))  # Memory intensive!
```

## Troubleshooting

### Problem: Rate Limit Errors

**Symptoms:** Many failed tasks, "429" errors in logs

**Solution:**
```python
# Reduce worker count
manager = SearchQueueManager(num_workers=2)  # Down from 3+

# Or add delays in config
config = {"per_page_delay": 2.0}  # 2 second delay between pages
manager.add_search("source", "query", config=config)
```

### Problem: Tasks Not Starting

**Symptoms:** Queue size stays constant, no progress

**Solution:**
```python
# Check if run_all() was called
manager.add_search("openalex", "query", limit=100)
manager.run_all()  # Don't forget this!

# Check worker count
print(manager.num_workers)  # Should be > 0
```

### Problem: Cache Not Working

**Symptoms:** Same search fetches from API each time

**Solution:**
```python
# Ensure resume_from_cache=True (default)
manager.add_search("openalex", "query", resume_from_cache=True)

# Check cache directory exists
print(manager.cache.db_path)  # Should show path
```

### Problem: Out of Memory

**Symptoms:** System freezes, slow performance

**Solution:**
```python
# Process results incrementally
manager.run_all()
for task_id in task_ids:
    papers = manager.get_results(task_id)
    save_to_disk(papers)
    # Clear from memory
    task = manager.queue.get_task(task_id)
    task.papers = []  # Free memory
```

## Performance Tips

### Optimize Worker Count

```python
import multiprocessing

# Use CPU count as base
cpu_count = multiprocessing.cpu_count()
optimal_workers = min(cpu_count, 5)  # Max 5 to respect APIs

manager = SearchQueueManager(num_workers=optimal_workers)
```

### Use Priority Effectively

```python
# Fetch small datasets first (quick wins)
manager.add_search("arxiv", "small query", limit=50, priority=0)

# Large datasets later
manager.add_search("openalex", "huge query", limit=10000, priority=10)
```

### Monitor Performance

```python
import time

start = time.time()
manager.run_all()
elapsed = time.time() - start

stats = manager.progress.compute_stats()
print(f"Time: {elapsed:.1f}s")
print(f"Papers: {stats.total_papers}")
print(f"Rate: {stats.papers_per_minute():.1f} papers/min")
```

## Integration with Existing Code

### Replace Old Orchestrator

**Before:**
```python
from srp.search.orchestrator import SearchOrchestrator

orchestrator = SearchOrchestrator()
results = await orchestrator.search_all_sources(
    sources=["openalex", "arxiv"],
    query="ML"
)
```

**After:**
```python
from srp.async_queue import SearchQueueManager

manager = SearchQueueManager(num_workers=3)
manager.add_search("openalex", "ML")
manager.add_search("arxiv", "ML")
manager.run_all()

results = manager.get_all_results()
```

### Use with CLI

See [docs/cli/queue_commands.md](../cli/queue_commands.md) for CLI integration.

## Advanced Topics

### Custom Strategies

```python
from srp.search.strategy import SearchStrategy, SearchRole

# Create custom strategy
strategy = SearchStrategy()
strategy.add_database(
    name="openalex",
    role=SearchRole.PRIMARY,
    priority=1
)

manager = SearchQueueManager(strategy=strategy)
```

### Task State Inspection

```python
# Get all tasks
all_tasks = manager.queue.get_all_tasks()

# Filter by status
from srp.async_queue import TaskStatus
failed_tasks = manager.queue.get_tasks_by_status(TaskStatus.FAILED)

for task in failed_tasks:
    print(f"Failed: {task.query} - {task.error}")
```

### Manual Cache Control

```python
# Clear cache for specific query
query_id = manager.cache.register_query(
    source="openalex",
    query="old query",
)
manager.cache.mark_completed(query_id)  # Force completion
```

## See Also

- [API Reference](API.md) - Complete API documentation
- [Examples](../../examples/queue_usage_examples.py) - Working code examples
- [Architecture](ARCHITECTURE.md) - Internal design
- [CLI Commands](../cli/queue_commands.md) - Command-line usage
