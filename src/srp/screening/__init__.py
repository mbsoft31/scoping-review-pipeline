"""
Screening subpackage for Phase 1.5 of the systematic review pipeline.

This package provides models for representing screening criteria and
results, a semantic matcher built on top of sentence transformers,
automatic and semi‑automatic screening logic, and a human‑in‑the‑loop
review queue manager.  These components enable intelligent filtering
of papers between Phase 1 (search) and Phase 2 (analysis).

The main entry points are:

* :class:`SemanticMatcher` – embed titles and abstracts and compute
  semantic similarities against criteria or domain vocabularies.
* :class:`AutoScreener` – screen individual papers or batches using
  inclusion/exclusion criteria, configurable thresholds and optional
  domain vocabularies.  Results include decisions, confidences,
  evidence snippets and tags.
* :class:`HITLReviewer` – manage a review queue for human reviewers
  when operating in semi‑automated or human‑in‑the‑loop modes.

The screening API is exposed via both the CLI (see ``srp screen`` and
``srp review`` commands) and the web dashboard routes defined in
``srp.web.routes``.
"""

from .models import (
    ScreeningCriterion,
    ScreeningDecision,
    ScreeningMode,
    DomainVocabulary,
    ScreeningResult,
    ScreeningBatch,
    ExclusionReason,
    InclusionTag,
)
from .semantic_matcher import SemanticMatcher
from .screener import AutoScreener
from .hitl import HITLReviewer

__all__ = [
    "ScreeningCriterion",
    "ScreeningDecision",
    "ScreeningMode",
    "DomainVocabulary",
    "ScreeningResult",
    "ScreeningBatch",
    "ExclusionReason",
    "InclusionTag",
    "SemanticMatcher",
    "AutoScreener",
    "HITLReviewer",
]