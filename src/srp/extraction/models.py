"""Models for data extraction.

This module defines a set of Pydantic models that describe the
structured information extracted from full‑text papers.  The
``ExtractedData`` model holds the high‑level characteristics of a
study, including the design, sample size, interventions, outcomes,
statistical results and quality indicators.  Enumerations provide
canonical names for common study designs.  These models are used by
the extraction logic and downstream analysis steps (quality
assessment, meta‑analysis, etc.).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StudyDesignType(str, Enum):
    """Enumerate common study design types.

    The values follow Cochrane and epidemiological terminology.  The
    ``UNKNOWN`` design is used when no keywords are detected.
    """

    RCT = "randomized_controlled_trial"
    COHORT = "cohort_study"
    CASE_CONTROL = "case_control"
    CROSS_SECTIONAL = "cross_sectional"
    SYSTEMATIC_REVIEW = "systematic_review"
    CASE_STUDY = "case_study"
    UNKNOWN = "unknown"


class Intervention(BaseModel):
    """Representation of an intervention or exposure.

    This structure can hold optional fields for dosage and duration to
    capture the intensity of exposure in the primary studies.  These
    fields are optional because not all studies report them.
    """

    name: str
    description: Optional[str] = None
    dosage: Optional[str] = None
    duration: Optional[str] = None


class Outcome(BaseModel):
    """Representation of an outcome measure.

    Each outcome can have an optional measurement (e.g. units), a
    timepoint at which the outcome was assessed, and associated
    statistics such as effect size, confidence intervals and p‑values.
    """

    name: str
    measurement: Optional[str] = None
    timepoint: Optional[str] = None
    effect_size: Optional[float] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    pvalue: Optional[float] = None


class ExtractedData(BaseModel):
    """Structured data extracted from a full‑text paper.

    The extraction process attempts to populate as many fields as
    possible.  Fields are optional when they are not available or
    cannot be reliably detected.  ``extraction_confidence`` provides
    a rough estimate of the reliability of the extraction, with 0.0
    representing unknown and 1.0 representing high confidence.
    """

    paper_id: str

    # Study characteristics
    study_design: str
    sample_size: Optional[int] = None
    population: Optional[str] = None
    setting: Optional[str] = None

    # Interventions and outcomes
    interventions: List[Intervention] = Field(default_factory=list)
    outcomes: List[Outcome] = Field(default_factory=list)

    # Statistical results
    pvalues: List[float] = Field(default_factory=list)
    effect_sizes: List[Dict[str, Any]] = Field(default_factory=list)
    statistical_methods: List[str] = Field(default_factory=list)

    # Quality indicators
    has_control_group: Optional[bool] = None
    randomization_method: Optional[str] = None
    blinding: Optional[str] = None

    # Metadata
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_confidence: float = Field(0.0, ge=0.0, le=1.0)