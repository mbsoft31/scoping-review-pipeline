"""Screening‑specific models and enumerations.

This module defines strongly typed representations for screening
criteria, decisions, domain vocabularies and screening results.  It
leverages Pydantic for data validation and serialization.  These
models are consumed by the semantic matcher, screener and HITL
reviewer as well as the CLI and web API.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime

from pydantic import BaseModel, Field


class ScreeningDecision(str, Enum):
    """Possible decisions after screening a paper."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    MAYBE = "maybe"
    UNSCREENED = "unscreened"


class ScreeningMode(str, Enum):
    """Supported screening workflows."""

    AUTO = "auto"  # Fully automated screening
    SEMI_AUTO = "semi_auto"  # Automated with review queue
    HITL = "hitl"  # Human in the loop
    MANUAL = "manual"  # Fully manual screening


class ExclusionReason(BaseModel):
    """Structured explanation for why a paper was excluded."""

    criterion_id: str
    criterion_name: str
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    evidence: List[str] = Field(default_factory=list)  # Text snippets supporting the exclusion


class InclusionTag(BaseModel):
    """Tag applied when a paper matches an inclusion criterion or vocabulary term."""

    tag_id: str
    tag_name: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # 'auto', 'human', 'hybrid'
    reasoning: Optional[str] = None


class ScreeningCriterion(BaseModel):
    """Definition of an inclusion or exclusion criterion."""

    criterion_id: str
    name: str
    description: str
    criterion_type: str  # 'inclusion' or 'exclusion'
    keywords: List[str] = Field(default_factory=list)
    semantic_query: Optional[str] = None
    weight: float = Field(1.0, ge=0.0)
    is_mandatory: bool = False


class DomainVocabulary(BaseModel):
    """Domain vocabulary for semantic matching and tagging."""

    domain: str
    concepts: List[str]
    synonyms: Dict[str, List[str]] = Field(default_factory=dict)
    embeddings: Optional[Dict[str, List[float]]] = None  # Reserved for future use


class ScreeningResult(BaseModel):
    """Screening result for a single paper."""

    paper_id: str
    decision: ScreeningDecision
    confidence: float = Field(ge=0.0, le=1.0)
    mode: ScreeningMode
    exclusion_reasons: List[ExclusionReason] = Field(default_factory=list)
    inclusion_tags: List[InclusionTag] = Field(default_factory=list)
    domain_matches: Dict[str, float] = Field(default_factory=dict)
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    human_override: Optional[bool] = None
    human_notes: Optional[str] = None
    screened_at: datetime = Field(default_factory=datetime.utcnow)
    screening_duration_ms: Optional[int] = None


class ScreeningBatch(BaseModel):
    """Container for a batch of screening results."""

    batch_id: str
    criteria: List[ScreeningCriterion]
    vocabulary: Optional[DomainVocabulary] = None
    mode: ScreeningMode
    results: List[ScreeningResult]
    total_papers: int
    included: int
    excluded: int
    maybe: int
    unscreened: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None