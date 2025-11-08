"""Configuration management using Pydantic Settings."""

from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API configuration
    openalex_email: Optional[str] = Field(None, description="Email for OpenAlex polite pool")
    semantic_scholar_api_key: Optional[str] = Field(None, description="S2 API key")
    crossref_email: Optional[str] = Field(None, description="Email for Crossref polite pool")

    # Rate limits (requests per second)
    openalex_rate_limit: float = Field(10.0, gt=0)
    semantic_scholar_rate_limit: float = Field(0.25, gt=0)
    crossref_rate_limit: float = Field(0.33, gt=0)

    # Search defaults
    default_start_date: str = "2018-01-01"
    default_end_date: str = "2025-12-31"
    default_page_size: int = Field(100, ge=1, le=200)

    # Directories
    output_dir: Path = Field(Path("output"))
    cache_dir: Path = Field(Path(".cache"))

    # Logging
    log_level: str = Field("INFO")
    log_format: str = Field("json", pattern="^(json|text)$")

    # LLM API keys (optional)
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key for GPT models")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key for Claude models")
    groq_api_key: Optional[str] = Field(None, description="Groq API key for fast Llama models")
    google_api_key: Optional[str] = Field(None, description="Google API key for Gemini models")
    together_api_key: Optional[str] = Field(None, description="Together AI API key for hosted models")

    # LLM routing configuration
    llm_mode: str = Field(
        "hybrid",
        description="LLM usage mode: 'local', 'hybrid' or 'api_only'",
    )
    llm_local_threshold: float = Field(
        0.75,
        description="Confidence threshold above which local results are accepted",
    )
    llm_cost_budget_per_paper: float = Field(
        0.05,
        description="Maximum spend per paper when using API models",
    )

    # Local model configuration
    local_model_dir: Path = Field(
        Path.home() / ".cache" / "srp_models",
        description="Directory where local models are stored",
    )
    quantized_llm_path: Optional[Path] = Field(
        None,
        description="Path to quantized LLM model file",
    )

    # Retry configuration
    max_retries: int = Field(5, ge=1, le=10)
    retry_backoff_factor: float = Field(2.0, gt=0)
    retry_max_wait: float = Field(60.0, gt=0)

    @field_validator("output_dir", "cache_dir")
    @classmethod
    def _create_dirs(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v


# Instantiate global settings
settings = Settings()