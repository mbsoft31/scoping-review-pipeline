# Deployment Guide - Scoping Review Pipeline

## Recommended Production Setup

### 1. Environment
- OS: Linux (Ubuntu), MacOS, or Windows
- Python: 3.11+
- Hardware: 4+ cores, 8GB+ RAM for fast batch operation

### 2. Installation
```
git clone https://github.com/mbsoft31/scoping-review-pipeline.git
cd scoping-review-pipeline
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration
- Populate `.env` with:
    - API keys for Semantic Scholar
    - Email for polite OpenAlex/Crossref requests
    - Output/cache directories as needed
- Tune `src/srp/config/adapter_config.py` for concurrent production load

### 4. Running Pipelines
- Use CLI/manager from your orchestrator script or batch job
- Adjust `num_workers` (3–8 recommended for high throughput)

### 5. Testing
- Run full suite with `pytest tests/queue/`

### 6. Metrics and Monitoring
- Start Prometheus scraper on `.metrics/metrics.prom`
- Load `config/grafana_dashboard.json` into Grafana for live monitoring

### 7. Reliability Practices
- Enable automatic retries and error handling (default)
- Configure cache resume to avoid data loss
- Use circuit breaker defaults for API issues
- Log all output for post-run audits
- Schedule daily batch jobs via systemd, cron, or Airflow

### 8. Updating & Rollback
- Update via `git pull` and `pip install -r requirements.txt`
- Rollback: `git checkout <previous-tag-or-commit>`

### 9. Security & Maintenance
- Store API keys securely (never commit sensitive keys)
- Review logs for unusual error patterns
- Rotate API keys and cache as needed

### 10. Support
- Open an issue for assistance or bug reports
- Check docs for troubleshooting, metrics, or scaling tips
