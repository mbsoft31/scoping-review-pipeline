# Utils Module

The **utils** module contains small helper utilities that are used across the pipeline.  They focus on rate limiting and logging.

## Rate Limiting

[`rate_limit.py`](../../src/srp/utils/rate_limit.py) implements a simple token‑bucket `RateLimiter` to control the rate of asynchronous API requests:

- The limiter is initialised with a `max_calls` and a `period`.  It allows up to `max_calls` requests per `period` seconds.
- The `async acquire()` method waits until a token is available before allowing the caller to proceed.  It uses an `asyncio.Lock` and sleeps as necessary.
- This limiter is used by search clients to comply with external API rate limits without relying on global sleep calls.

## Logging

[`logging.py`](../../src/srp/utils/logging.py) provides a `get_logger(name: str)` function that configures a logger with two formats:

- When `settings.log_json` is true, log messages are emitted as JSON objects with fields such as `level`, `time`, `name` and `message`, suitable for structured logging systems.
- Otherwise, logs are printed in a human‑friendly plain‑text format with coloured levels.  The logger is configured to propagate messages only once per name.

All modules use this helper to obtain a module‑scoped logger, ensuring consistent logging across the project.