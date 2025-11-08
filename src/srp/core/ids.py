"""ID normalization and generation utilities."""

import hashlib
from typing import Optional


def generate_paper_id(source: str, external_id: str) -> str:
    """Generate a unique paper ID from source and external identifier."""
    return f"{source}:{external_id}"


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    """Normalize DOI to canonical form."""
    if not doi:
        return None
    doi = doi.lower().strip()
    prefixes = [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
        "doi:",
    ]
    for prefix in prefixes:
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip() or None


def normalize_arxiv_id(arxiv_id: Optional[str]) -> Optional[str]:
    """Normalize arXiv ID to canonical form."""
    if not arxiv_id:
        return None
    arxiv_id = arxiv_id.strip()
    if arxiv_id.lower().startswith("arxiv:"):
        arxiv_id = arxiv_id[6:]
    if "v" in arxiv_id:
        parts = arxiv_id.rsplit("v", 1)
        if parts[-1].isdigit():
            arxiv_id = parts[0]
    return arxiv_id.strip() or None


def compute_title_hash(title: str) -> str:
    """Compute normalized hash of a title for deduplication."""
    import re
    normalized = re.sub(r'[^\w\s]', '', title.lower())
    normalized = ' '.join(normalized.split())
    return hashlib.md5(normalized.encode()).hexdigest()