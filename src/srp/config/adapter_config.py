"""Per-adapter configuration for rate limits and behavior."""

from typing import Dict
from pydantic import BaseModel, Field


class AdapterRateConfig(BaseModel):
    """Rate limit configuration for a search adapter."""
    
    rate: float = Field(gt=0, description="Requests per second")
    burst: int = Field(gt=0, description="Burst capacity (initial tokens)")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    max_retries: int = Field(default=5, ge=1, le=10, description="Max retry attempts")


class AdapterConfig(BaseModel):
    """Complete adapter configuration."""
    
    rate_limit: AdapterRateConfig
    page_size: int = Field(default=100, ge=1, le=200, description="Results per page")
    enable_caching: bool = Field(default=True, description="Enable result caching")
    max_concurrent: int = Field(default=3, ge=1, le=10, description="Max concurrent requests")


# Default configurations for each adapter
# These are based on each API's documented rate limits and best practices
DEFAULT_ADAPTER_CONFIGS: Dict[str, AdapterConfig] = {
    "openalex": AdapterConfig(
        rate_limit=AdapterRateConfig(
            rate=10.0,  # 10 req/s for polite pool
            burst=15,   # Allow burst of 15 requests
            timeout=30.0,
            max_retries=5,
        ),
        page_size=100,
        enable_caching=True,
        max_concurrent=5,
    ),
    "semantic_scholar": AdapterConfig(
        rate_limit=AdapterRateConfig(
            rate=1.0,   # 1 req/s (conservative for S2)
            burst=3,    # Allow burst of 3 requests
            timeout=30.0,
            max_retries=5,
        ),
        page_size=20,
        enable_caching=True,
        max_concurrent=3,
    ),
    "arxiv": AdapterConfig(
        rate_limit=AdapterRateConfig(
            rate=0.33,  # ~1 req per 3 seconds (arXiv requirement)
            burst=1,    # No burst for arXiv
            timeout=60.0,  # Longer timeout for arXiv
            max_retries=3,
        ),
        page_size=50,
        enable_caching=True,
        max_concurrent=1,  # Serial requests for arXiv
    ),
    "crossref": AdapterConfig(
        rate_limit=AdapterRateConfig(
            rate=50.0,  # 50 req/s for polite pool
            burst=100,  # Large burst allowed
            timeout=30.0,
            max_retries=5,
        ),
        page_size=100,
        enable_caching=True,
        max_concurrent=10,
    ),
}


def get_adapter_config(adapter_name: str) -> AdapterConfig:
    """Get configuration for an adapter.
    
    Args:
        adapter_name: Name of the adapter ("openalex", "semantic_scholar", etc.)
        
    Returns:
        AdapterConfig for the specified adapter
        
    Raises:
        ValueError: If adapter_name is not recognized
    """
    if adapter_name not in DEFAULT_ADAPTER_CONFIGS:
        raise ValueError(
            f"Unknown adapter: {adapter_name}. "
            f"Valid options: {list(DEFAULT_ADAPTER_CONFIGS.keys())}"
        )
    return DEFAULT_ADAPTER_CONFIGS[adapter_name]
