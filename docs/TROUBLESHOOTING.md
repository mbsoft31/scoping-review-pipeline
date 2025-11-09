# Troubleshooting Guide - Scoping Review Pipeline

## Common Issues and Solutions

### 1. Rate Limit Errors
- **Symptoms:** 429 Too Many Requests from Semantic Scholar, OpenAlex, Crossref
- **Solution:**
    - Reduce `num_workers` in SearchQueueManager
    - Provide API keys (Semantic Scholar) in `.env`
    - Wait and retry, or tune burst and rate config in `adapter_config.py`

### 2. Network Timeouts or Unreachable APIs
- **Symptoms:** Requests to sources hang or timeout
- **Solution:**
    - Check local internet/firewall
    - Increase `timeout` in adapter config
    - Enable retries (handled automatically by error handler)
    - Ensure remote APIs are operational

### 3. Task Fails with Circuit Breaker OPEN
- **Symptoms:** Many tasks are skipped, CLI prints "Circuit breaker is OPEN"
- **Solution:**
    - Queue detected excessive failures in a source, temporarily blocking requests
    - Check error logs, API rate limits, and recover after a minute
    - Restart pipeline once diagnostics are performed

### 4. Resume from Cache Not Working
- **Symptoms:** After interruption, searches restart from scratch
- **Solution:**
    - Ensure correct cache_dir in `.env` and configuration
    - Update package to latest version (cache bug may be fixed)
    - Manually re-run with resume enabled

### 5. Poor Search Recall or Quality
- **Symptoms:** Pipeline finds few relevant papers
- **Solution:**
    - Expand queries in batch processor (add synonyms and domain terms)
    - Tune adapter filters and settings
    - Validate result deduplication is functioning

### 6. Metrics Not Exporting or Incorrect
- **Symptoms:** Metrics files not present, Grafana not populating
- **Solution:**
    - Enable metrics in SearchQueueManager or batch runs
    - Check `.metrics/` folder and Prometheus scrape path
    - Validate Grafana dashboard setup

---

## Logging and Diagnostics
- Review logs in cache/output directory for detailed errors
- Enable DEBUG log level in `.env` or settings if needed
- Log files are JSON-formatted or plain text for troubleshooting

---

## Support Channels
- GitHub Issues: https://github.com/mbsoft31/scoping-review-pipeline/issues
- Discussions: https://github.com/mbsoft31/scoping-review-pipeline/discussions
- Email: bekhouche.mouadh@univ-oeb.dz
