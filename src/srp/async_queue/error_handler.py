"""Intelligent error handling with classification and retry strategies."""

import asyncio
from enum import Enum
from typing import Optional, Callable, Any, Dict
from datetime import datetime, timedelta
import random
import httpx

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ErrorType(Enum):
    """Classification of error types for appropriate handling."""
    RATE_LIMIT = "rate_limit"      # 429 errors - need backoff
    NETWORK = "network"              # Connection, timeout - transient
    API_ERROR = "api_error"          # 4xx/5xx errors - may be persistent
    PARSE_ERROR = "parse_error"      # Data parsing failures - don't retry
    VALIDATION = "validation"        # Invalid input - don't retry
    UNKNOWN = "unknown"              # Unclassified - retry conservatively


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failing, reject requests immediately
    HALF_OPEN = "half_open"    # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern for failing services.
    
    Prevents cascading failures by temporarily blocking requests to
    failing services. After a cooldown period, it allows test requests
    to check if the service has recovered.
    
    States:
    - CLOSED: Normal operation, all requests pass through
    - OPEN: Service is failing, reject requests immediately
    - HALF_OPEN: Testing recovery, allow limited requests
    
    Example:
        >>> breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
        >>> result = await breaker.call(my_async_function, arg1, arg2)
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            success_threshold: Successful calls needed to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            Exception: If circuit is OPEN or func raises
        """
        async with self._lock:
            # Check circuit state
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise Exception(
                        f"Circuit breaker is OPEN. Service failing. "
                        f"Retry in {self._time_until_reset():.1f}s"
                    )
        
        # Execute function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    logger.info("Circuit breaker closing - service recovered")
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
    
    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                logger.warning("Circuit breaker opening - recovery failed")
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit breaker opening - {self.failure_count} consecutive failures"
                )
                self.state = CircuitState.OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.last_failure_time:
            return True
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _time_until_reset(self) -> float:
        """Calculate seconds until circuit can attempt reset."""
        if not self.last_failure_time:
            return 0.0
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return max(0.0, self.recovery_timeout - elapsed)
    
    def get_state(self) -> str:
        """Get current circuit state."""
        return self.state.value


class ErrorHandler:
    """
    Intelligent error handler with classification and retry strategies.
    
    Provides:
    - Error type classification
    - Retry decision logic
    - Adaptive backoff calculation
    - Per-service circuit breakers
    
    Example:
        >>> handler = ErrorHandler()
        >>> error_type = handler.classify_error(exception)
        >>> if handler.should_retry(error_type, attempt=1, max_attempts=5):
        ...     backoff = await handler.calculate_backoff(error_type, attempt=1)
        ...     await asyncio.sleep(backoff)
    """
    
    def __init__(self):
        """Initialize error handler."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    def classify_error(self, error: Exception) -> ErrorType:
        """
        Classify error type for appropriate handling.
        
        Args:
            error: Exception to classify
            
        Returns:
            ErrorType enum value
        """
        # HTTP status errors
        if isinstance(error, httpx.HTTPStatusError):
            status = error.response.status_code
            if status == 429:
                return ErrorType.RATE_LIMIT
            elif 400 <= status < 500:
                # Client errors - usually don't retry except 429
                return ErrorType.API_ERROR
            elif 500 <= status < 600:
                # Server errors - retry with backoff
                return ErrorType.API_ERROR
        
        # Network errors - transient, always retry
        elif isinstance(error, (httpx.ConnectError, httpx.TimeoutException, 
                                httpx.NetworkError, httpx.ReadTimeout)):
            return ErrorType.NETWORK
        
        # Parsing errors - don't retry
        elif isinstance(error, (ValueError, KeyError, AttributeError, TypeError)):
            return ErrorType.PARSE_ERROR
        
        # Unknown - handle conservatively
        return ErrorType.UNKNOWN
    
    def should_retry(self, error_type: ErrorType, attempt: int, max_attempts: int) -> bool:
        """
        Determine if error should be retried.
        
        Args:
            error_type: Type of error that occurred
            attempt: Current attempt number (1-indexed)
            max_attempts: Maximum attempts allowed
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= max_attempts:
            return False
        
        # Always retry rate limits and network errors
        if error_type in (ErrorType.RATE_LIMIT, ErrorType.NETWORK):
            return True
        
        # Retry API errors with caution
        if error_type == ErrorType.API_ERROR:
            return attempt < max_attempts - 1
        
        # Never retry parse/validation errors (they won't fix themselves)
        if error_type in (ErrorType.PARSE_ERROR, ErrorType.VALIDATION):
            return False
        
        # Unknown errors: retry conservatively (only first 2 attempts)
        return attempt < 2
    
    async def calculate_backoff(
        self,
        error_type: ErrorType,
        attempt: int,
        base_delay: float = 2.0,
        max_delay: float = 60.0
    ) -> float:
        """
        Calculate backoff delay based on error type and attempt.
        
        Uses different strategies per error type:
        - Rate limit: Exponential backoff (aggressive)
        - Network: Linear backoff (transient issues)
        - API: Moderate exponential backoff
        - Unknown: Conservative exponential backoff
        
        Adds jitter to prevent thundering herd.
        
        Args:
            error_type: Type of error
            attempt: Current attempt number (1-indexed)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            
        Returns:
            Delay in seconds (float)
        """
        if error_type == ErrorType.RATE_LIMIT:
            # Exponential backoff for rate limits
            delay = min(base_delay * (2 ** attempt), max_delay)
        elif error_type == ErrorType.NETWORK:
            # Linear backoff for network issues (usually transient)
            delay = min(base_delay * attempt, max_delay)
        elif error_type == ErrorType.API_ERROR:
            # Moderate exponential backoff for API errors
            delay = min(base_delay * (1.5 ** attempt), max_delay)
        else:
            # Conservative backoff for unknown errors
            delay = min(base_delay * (3 ** attempt), max_delay)
        
        # Add jitter (±10%) to prevent thundering herd
        jitter = delay * 0.1 * random.uniform(-1, 1)
        final_delay = max(0.1, delay + jitter)  # Minimum 0.1s
        
        logger.debug(
            f"Calculated backoff: {final_delay:.2f}s "
            f"(type={error_type.value}, attempt={attempt})"
        )
        
        return final_delay
    
    async def get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """
        Get or create circuit breaker for service.
        
        Args:
            service: Service identifier (e.g., "openalex", "semantic_scholar")
            
        Returns:
            CircuitBreaker instance for the service
        """
        async with self._lock:
            if service not in self.circuit_breakers:
                self.circuit_breakers[service] = CircuitBreaker(
                    failure_threshold=5,
                    recovery_timeout=60.0,
                    success_threshold=2,
                )
            return self.circuit_breakers[service]
    
    def get_circuit_states(self) -> Dict[str, str]:
        """
        Get circuit breaker states for all services.
        
        Returns:
            Dict mapping service name to circuit state
        """
        return {
            service: breaker.get_state()
            for service, breaker in self.circuit_breakers.items()
        }
