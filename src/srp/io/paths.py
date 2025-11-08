"""Output directory and file path management."""

from pathlib import Path
from datetime import datetime
from typing import Optional

from ..config.settings import settings


def create_output_dir(phase: str, timestamp: Optional[datetime] = None) -> Path:
    if timestamp is None:
        timestamp = datetime.now()
    dirname = f"{phase}_{timestamp.strftime('%Y%m%d_%H%M%S')}"
    dirpath = settings.output_dir / dirname
    dirpath.mkdir(parents=True, exist_ok=True)
    return dirpath


def get_cache_path(cache_type: str = "searches") -> Path:
    cache_path = settings.cache_dir / cache_type
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path