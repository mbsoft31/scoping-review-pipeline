"""Per-adapter configuration with rate limiting and retry settings."""

from typing import Dict
from pydantic import BaseModel, Field


class AdapterRateConfig(BaseModel):
    """Rate limit configuration for a search adapter."""
    rate: float = Field(gt=0, description="Requests per second")
    burst: int = Field(gt=0, description="Burst capacity (max tokens)")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    max_retries: int = Field(default=5, description="Maximum retry attempts")


class AdapterConfig(BaseModel):
    """Complete adapter configuration."""
    rate_limit: AdapterRateConfig
    page_size: int = Field(default=100, ge=1, le=200, description="Results per page")
    enable_caching: bool = Field(default=True, description="Enable result caching")


# Default configurations for each adapter
# These are based on each API's rate limits and best practices
DEFAULT_ADAPTER_CONFIGS: Dict[str, AdapterConfig] = {
    "openalex": AdapterConfig(
        rate_limit=AdapterRateConfig(
            rate=10.0,  # OpenAlex: 10 req/s for polite pool
            burst=15,   # Allow burst for initial requests
            timeout=30.0,
            max_retries=5,
        ),
        page_size=100,
        enable_caching=True,
    ),
    "semantic_scholar": AdapterConfig(
        rate_limit=AdapterRateConfig(
            rate=1.0,   # S2: 1 req/s (up from 0.25)
            burst=3,    # Allow small burst
            timeout=30.0,
            max_retries=5,
        ),
        page_size=20,   # S2 supports max 100, but 20 is safer
        enable_caching=True,
    ),
    "arxiv": AdapterConfig(
        rate_limit=AdapterRateConfig(
            rate=0.33,  # arXiv: 1 req per 3 seconds
            burst=1,    # No burst for arXiv
            timeout=30.0,
            max_retries=3,  # Fewer retries for arXiv
        ),
        page_size=50,
        enable_caching=True,
    ),
    "crossref": AdapterConfig(
        rate_limit=AdapterRateConfig(
            rate=50.0,  # Crossref: 50 req/s for polite pool
            burst=100,  # Large burst allowed
            timeout=30.0,
            max_retries=5,
        ),
        page_size=100,
        enable_caching=True,
    ),
}


def get_adapter_config(adapter_name: str) -> AdapterConfig:
    """Get configuration for a specific adapter.
    
    Args:
        adapter_name: Name of the adapter ("openalex", "semantic_scholar", etc.)
        
    Returns:
        AdapterConfig for the specified adapter
        
    Raises:
        KeyError: If adapter name is not recognized
    """
    if adapter_name not in DEFAULT_ADAPTER_CONFIGS:
        raise KeyError(
            f"Unknown adapter '{adapter_name}'. "
            f"Known adapters: {', '.join(DEFAULT_ADAPTER_CONFIGS.keys())}"
        )
    return DEFAULT_ADAPTER_CONFIGS[adapter_name]