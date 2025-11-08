"""Structured logging configuration."""

import logging
import json
import sys
from typing import Any, Dict

try:
    # Import settings for logging configuration. This can fail when
    # pydantic_settings is not installed (e.g., in minimal test environments).
    from ..config.settings import settings  # type: ignore
except Exception:
    # Fallback settings with reasonable defaults to avoid import errors during
    # testing. These defaults can be overridden via environment variables if
    # needed.
    class _FallbackSettings:
        log_format: str = "json"
        log_level: str = "INFO"

    settings = _FallbackSettings()  # type: ignore


class JSONFormatter(logging.Formatter):
    """Format logs as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            log_data.update(record.extra)  # type: ignore
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if settings.log_format == "json":
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    return logger