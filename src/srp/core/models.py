"""Core domain models for papers, authors and references."""

from datetime import date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class Author(BaseModel):
    """Author information."""
    name: str
    author_id: Optional[str] = None
    orcid: Optional[str] = None
    affiliation: Optional[str] = None


class Source(BaseModel):
    """Source database information."""
    database: str = Field(..., description="Source database name")
    query: str = Field(..., description="Query that retrieved this paper")
    timestamp: str = Field(..., description="ISO 8601 timestamp of retrieval")
    page: Optional[int] = None
    cursor: Optional[str] = None


class Paper(BaseModel):
    """Core paper model with normalized fields."""

    paper_id: str = Field(..., description="Internal unique ID")
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None

    # Bibliographic metadata
    title: str
    abstract: Optional[str] = None
    authors: List[Author] = Field(default_factory=list)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    publication_date: Optional[date] = None
    venue: Optional[str] = None
    publisher: Optional[str] = None

    # Content metadata
    fields_of_study: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

    # Citation metrics
    citation_count: int = Field(0, ge=0)
    influential_citation_count: int = Field(0, ge=0)
    reference_count: int = Field(0, ge=0)

    # Access
    is_open_access: bool = False
    open_access_pdf: Optional[str] = None

    # External identifiers (normalized)
    external_ids: Dict[str, str] = Field(default_factory=dict)

    # Source tracking
    source: Source
    raw_data: Optional[Dict[str, Any]] = Field(None, exclude=True)

    @field_validator("doi")
    @classmethod
    def _normalize_doi(cls, v: Optional[str]) -> Optional[str]:
        """Normalize DOI: lowercase, remove prefixes."""
        if not v:
            return None
        doi = v.lower().strip()
        for prefix in ["https://doi.org/", "http://dx.doi.org/", "doi:"]:
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
        return doi or None

    @field_validator("arxiv_id")
    @classmethod
    def _normalize_arxiv(cls, v: Optional[str]) -> Optional[str]:
        """Normalize arXiv ID."""
        if not v:
            return None
        arxiv = v.strip()
        if arxiv.lower().startswith("arxiv:"):
            arxiv = arxiv[6:]
        return arxiv or None


class Reference(BaseModel):
    """Citation/reference relationship."""
    citing_paper_id: str
    cited_doi: Optional[str] = None
    cited_paper_id: Optional[str] = None
    cited_title: Optional[str] = None
    source: str
    context: Optional[str] = None


class DeduplicationCluster(BaseModel):
    """Group of duplicate papers."""
    canonical_id: str
    duplicate_ids: List[str]
    match_type: str = Field(..., description="doi, arxiv, title_fuzzy")
    confidence: float = Field(..., ge=0.0, le=1.0)