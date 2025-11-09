"""Intelligent error handling with classification and retry strategies."""

import asyncio
from enum import Enum
from typing import Optional, Callable, Any, Dict
from datetime import datetime, timedelta
import httpx

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ErrorType(Enum):
    """Classification of error types for appropriate handling."""
    RATE_LIMIT = "rate_limit"      # 429 errors
    NETWORK = "network"              # Connection, timeout
    API_ERROR = "api_error"          # 4xx/5xx errors
    PARSE_ERROR = "parse_error"      # Data parsing failures
    VALIDATION = "validation"        # Invalid input
    UNKNOWN = "unknown"              # Unclassified errors


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failing, reject requests
    HALF_OPEN = "half_open"    # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker pattern for failing services.
    
    Prevents cascading failures by temporarily blocking requests
    to services that are failing consistently.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service failing, requests rejected immediately
    - HALF_OPEN: Testing if service recovered
    
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
            success_threshold: Successful calls needed to close circuit from half-open
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
            
        Returns:
            Result from func
            
        Raises:
            Exception: If circuit is OPEN or func raises
        """
        # Check if should attempt reset
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info("Circuit breaker entering HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise Exception(
                    f"Circuit breaker is OPEN (last failure: "
                    f"{(datetime.now() - self.last_failure_time).total_seconds():.1f}s ago)"
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.debug(
                f"Circuit breaker success {self.success_count}/{self.success_threshold}"
            )
            
            if self.success_count >= self.success_threshold:
                logger.info("Circuit breaker closing (service recovered)")
                self.state = CircuitState.CLOSED
                self.success_count = 0
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test - back to OPEN
            logger.warning("Circuit breaker reopening (recovery test failed)")
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker opening after {self.failure_count} failures"
            )
            self.state = CircuitState.OPEN
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if not self.last_failure_time:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        logger.info("Circuit breaker manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None


class ErrorHandler:
    """
    Intelligent error handler with classification and retry strategies.
    
    Features:
    - Automatic error classification
    - Retry decision logic based on error type
    - Adaptive backoff calculation
    - Per-service circuit breakers
    
    Example:
        >>> handler = ErrorHandler()
        >>> error_type = handler.classify_error(exception)
        >>> should_retry = handler.should_retry(error_type, attempt=1, max_attempts=5)
        >>> if should_retry:
        ...     backoff = await handler.calculate_backoff(error_type, attempt=1)
        ...     await asyncio.sleep(backoff)
    """
    
    def __init__(self):
        """Initialize error handler."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
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
                return ErrorType.API_ERROR
            elif 500 <= status < 600:
                return ErrorType.API_ERROR
        
        # Network errors
        elif isinstance(error, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)):
            return ErrorType.NETWORK
        
        # Parsing errors
        elif isinstance(error, (ValueError, KeyError, AttributeError, TypeError)):
            return ErrorType.PARSE_ERROR
        
        # Unknown
        return ErrorType.UNKNOWN
    
    def should_retry(self, error_type: ErrorType, attempt: int, max_attempts: int) -> bool:
        """
        Determine if error should be retried.
        
        Args:
            error_type: Type of error that occurred
            attempt: Current attempt number (1-indexed)
            max_attempts: Maximum allowed attempts
            
        Returns:
            True if should retry, False otherwise
        """
        if attempt >= max_attempts:
            return False
        
        # Always retry rate limits and network errors
        if error_type in (ErrorType.RATE_LIMIT, ErrorType.NETWORK):
            return True
        
        # Retry API errors with backoff
        if error_type == ErrorType.API_ERROR:
            return attempt < max_attempts - 1
        
        # Don't retry parse/validation errors (likely bug)
        if error_type in (ErrorType.PARSE_ERROR, ErrorType.VALIDATION):
            return False
        
        # Unknown errors: retry conservatively
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
        
        Uses different strategies for different error types:
        - Rate limits: Exponential backoff
        - Network: Linear backoff
        - API errors: Exponential backoff
        - Others: Conservative exponential
        
        Args:
            error_type: Type of error
            attempt: Current attempt number (1-indexed)
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            
        Returns:
            Delay in seconds (with jitter)
        """
        if error_type == ErrorType.RATE_LIMIT:
            # Exponential backoff for rate limits
            delay = min(base_delay * (2 ** attempt), max_delay)
        
        elif error_type == ErrorType.NETWORK:
            # Linear backoff for network issues
            delay = min(base_delay * attempt, max_delay)
        
        elif error_type == ErrorType.API_ERROR:
            # Exponential backoff for API errors
            delay = min(base_delay * (1.5 ** attempt), max_delay)
        
        else:
            # Conservative backoff for unknown errors
            delay = min(base_delay * (3 ** attempt), max_delay)
        
        # Add jitter (±10%) to prevent thundering herd
        jitter = delay * 0.1 * (hash(str(datetime.now())) % 100) / 100
        final_delay = delay + jitter
        
        logger.debug(
            f"Calculated backoff: {final_delay:.2f}s "
            f"(type={error_type.value}, attempt={attempt})"
        )
        
        return final_delay
    
    def get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """
        Get or create circuit breaker for a service.
        
        Args:
            service: Service name (e.g., "openalex", "semantic_scholar")
            
        Returns:
            CircuitBreaker instance for the service
        """
        if service not in self.circuit_breakers:
            logger.debug(f"Creating circuit breaker for {service}")
            self.circuit_breakers[service] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60.0,
                success_threshold=2,
            )
        return self.circuit_breakers[service]
    
    def reset_circuit_breaker(self, service: str):
        """
        Manually reset circuit breaker for a service.
        
        Args:
            service: Service name to reset
        """
        if service in self.circuit_breakers:
            self.circuit_breakers[service].reset()
    
    def get_circuit_status(self, service: str) -> Optional[str]:
        """
        Get circuit breaker status for a service.
        
        Args:
            service: Service name
            
        Returns:
            Circuit state ("closed", "open", "half_open") or None if no breaker exists
        """
        if service in self.circuit_breakers:
            return self.circuit_breakers[service].state.value
        return None