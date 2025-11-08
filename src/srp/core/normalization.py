"""Text and metadata normalization utilities."""

import re
from datetime import datetime, date
from typing import Optional


def normalize_title(title: str) -> str:
    """Normalize a title for comparison."""
    if not title:
        return ""
    title = title.lower()
    title = re.sub(r'[^\w\s]', '', title)
    title = ' '.join(title.split())
    return title


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse various date formats to a date object."""
    if not date_str:
        return None
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m",
        "%Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:len(fmt)], fmt)
            return dt.date()
        except ValueError:
            continue
    return None


def extract_year(date_obj: Optional[date]) -> Optional[int]:
    """Extract year from a date object."""
    return date_obj.year if date_obj else None


def clean_abstract(abstract: Optional[str], max_length: int = 5000) -> Optional[str]:
    """Clean and truncate an abstract."""
    if not abstract:
        return None
    abstract = ' '.join(abstract.split())
    if len(abstract) > max_length:
        abstract = abstract[:max_length] + "..."
    return abstract