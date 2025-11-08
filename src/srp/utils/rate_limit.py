"""Rate limiting utilities using a token bucket algorithm."""

import asyncio
import time
from typing import Optional


class RateLimiter:
    """Token bucket rate limiter for async operations."""

    def __init__(self, rate: float, period: float = 1.0, burst: Optional[int] = None) -> None:
        self.rate = rate
        self.period = period
        self.burst = burst or int(rate)
        self._tokens: float = float(self.burst)
        self._last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_update
                self._tokens = min(self.burst, self._tokens + elapsed * (self.rate / self.period))
                self._last_update = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                tokens_needed = tokens - self._tokens
                wait_time = (tokens_needed * self.period) / self.rate
                await asyncio.sleep(wait_time)