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

    date_str = str(date_str).strip()
    if not date_str:
        return None

    # Try formats from most specific to least specific
    formats = [
        ("%Y-%m-%d", 10, lambda s: len(s) >= 10 and s[4] == '-' and s[7] == '-'),
        ("%Y/%m/%d", 10, lambda s: len(s) >= 10 and s[4] == '/' and s[7] == '/'),
        ("%d-%m-%Y", 10, lambda s: len(s) >= 10 and s[2] == '-' and s[5] == '-'),
        ("%d/%m/%Y", 10, lambda s: len(s) >= 10 and s[2] == '/' and s[5] == '/'),
        ("%Y-%m", 7, lambda s: len(s) >= 7 and s[4] == '-' and s[:4].isdigit()),
        ("%Y", 4, lambda s: len(s) >= 4 and s[:4].isdigit()),
    ]

    for fmt, length, validator in formats:
        if not validator(date_str):
            continue

        try:
            test_str = date_str[:length]
            dt = datetime.strptime(test_str, fmt)

            # Validate the parsed date
            if dt.year < 1900 or dt.year > 2100:
                continue

            return dt.date()
        except (ValueError, IndexError):
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
    # Return None if after cleaning it's empty
    if not abstract:
        return None
    if len(abstract) > max_length:
        abstract = abstract[:max_length] + "..."
    return abstract