import pytest
from srp.async_queue.error_handler import ErrorHandler, ErrorType

def test_should_retry_logic():
    eh = ErrorHandler()
    assert eh.should_retry(ErrorType.RATE_LIMIT, 1, 5)
    assert not eh.should_retry(ErrorType.PARSE_ERROR, 1, 5)
    assert eh.should_retry(ErrorType.API_ERROR, 2, 5)
    assert not eh.should_retry(ErrorType.API_ERROR, 5, 5)
