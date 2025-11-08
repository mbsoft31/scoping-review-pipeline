"""Models for risk‑of‑bias and quality assessment.

These Pydantic models capture the outputs of a risk‑of‑bias (RoB)
assessment.  ``BiasJudgment`` enumerates the possible judgments for
each bias domain.  ``RiskOfBiasAssessment`` aggregates the domain
assessments and summarises them into an overall judgment with a
confidence score.  These models can be enriched with metadata
indicating whether a human reviewer has overridden the automated
assessment.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BiasJudgment(str, Enum):
    """Possible risk‑of‑bias judgments for a domain or overall study."""

    LOW = "low"
    SOME_CONCERNS = "some_concerns"
    HIGH = "high"
    UNCLEAR = "unclear"


class RiskOfBiasAssessment(BaseModel):
    """Container for the results of a risk‑of‑bias assessment."""

    paper_id: str
    tool: str
    overall_judgment: BiasJudgment
    overall_confidence: float = Field(ge=0.0, le=1.0)
    domain_assessments: List[Dict] = Field(default_factory=list)
    requires_human_review: bool = False
    reviewed_by: Optional[str] = None
    human_override: Optional[BiasJudgment] = None
    assessed_at: datetime = Field(default_factory=datetime.utcnow)