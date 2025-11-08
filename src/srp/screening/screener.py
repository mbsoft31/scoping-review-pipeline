"""Automated screening engine with semantic understanding.

This module implements the logic to screen papers according to
inclusion/exclusion criteria and domain vocabularies using semantic
matching.  The core class :class:`AutoScreener` encapsulates
configurable thresholds for automatic decisions and returns
``ScreeningResult`` objects capturing the outcome and evidence.
"""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime
import time

from ..core.models import Paper
from .models import (
    ScreeningDecision,
    ScreeningMode,
    ScreeningCriterion,
    ScreeningResult,
    ExclusionReason,
    InclusionTag,
    DomainVocabulary,
)
from .semantic_matcher import SemanticMatcher
from ..utils.logging import get_logger

logger = get_logger(__name__)


class AutoScreener:
    """Automatic and semi‑automatic paper screening.

    The screener uses a :class:`SemanticMatcher` to compute semantic
    similarity scores between the paper text and each inclusion or
    exclusion criterion.  Decisions are derived from these scores
    according to configurable thresholds (``auto_threshold`` and
    ``maybe_threshold``).  Domain vocabulary matches are optionally
    added as inclusion tags.
    """

    def __init__(
        self,
        matcher: Optional[SemanticMatcher] = None,
        auto_threshold: float = 0.75,
        maybe_threshold: float = 0.5,
    ) -> None:
        self.matcher = matcher or SemanticMatcher()
        self.auto_threshold = auto_threshold
        self.maybe_threshold = maybe_threshold

    def screen_paper(
        self,
        paper: Paper,
        inclusion_criteria: List[ScreeningCriterion],
        exclusion_criteria: List[ScreeningCriterion],
        vocabulary: Optional[DomainVocabulary] = None,
        mode: ScreeningMode = ScreeningMode.AUTO,
    ) -> ScreeningResult:
        """Screen a single paper and return a ``ScreeningResult``."""
        start_time = time.time()
        # Check exclusions first
        exclusion_reasons: List[ExclusionReason] = []
        max_excl_conf = 0.0
        for c in exclusion_criteria:
            matches, conf, evidence = self.matcher.match_criterion(paper, c, threshold=self.maybe_threshold)
            if matches:
                exclusion_reasons.append(
                    ExclusionReason(
                        criterion_id=c.criterion_id,
                        criterion_name=c.name,
                        confidence=conf,
                        explanation=c.description,
                        evidence=evidence,
                    )
                )
                max_excl_conf = max(max_excl_conf, conf * c.weight)
        # Immediate exclusion if high confidence
        if max_excl_conf >= self.auto_threshold:
            decision = ScreeningDecision.EXCLUDE
            confidence = max_excl_conf
        else:
            inclusion_tags: List[InclusionTag] = []
            inclusion_scores: List[float] = []
            # Evaluate inclusion criteria
            for c in inclusion_criteria:
                matches, conf, evidence = self.matcher.match_criterion(paper, c, threshold=self.maybe_threshold)
                if matches:
                    inclusion_tags.append(
                        InclusionTag(
                            tag_id=c.criterion_id,
                            tag_name=c.name,
                            category="criterion",
                            confidence=conf,
                            source="auto",
                            reasoning=f"Matched: {c.description}",
                        )
                    )
                    inclusion_scores.append(conf * c.weight)
            # Mandatory criteria must all be matched
            mandatory = [c for c in inclusion_criteria if c.is_mandatory]
            if mandatory and not all(
                any(tag.tag_id == c.criterion_id for tag in inclusion_tags) for c in mandatory
            ):
                decision = ScreeningDecision.EXCLUDE
                confidence = 1.0
                exclusion_reasons.append(
                    ExclusionReason(
                        criterion_id="mandatory",
                        criterion_name="Missing mandatory criteria",
                        confidence=1.0,
                        explanation="Paper does not meet all mandatory inclusion criteria",
                        evidence=[],
                    )
                )
            else:
                # Compute average inclusion score
                avg_incl = sum(inclusion_scores) / len(inclusion_scores) if inclusion_scores else 0.0
                if avg_incl >= self.auto_threshold:
                    decision = ScreeningDecision.INCLUDE
                    confidence = avg_incl
                elif avg_incl >= self.maybe_threshold:
                    decision = ScreeningDecision.MAYBE
                    confidence = avg_incl
                else:
                    decision = ScreeningDecision.EXCLUDE
                    confidence = 1.0 - avg_incl
        # Vocabulary tagging
        domain_matches: Dict[str, float] = {}
        inclusion_tags: List[InclusionTag] = [] if 'inclusion_tags' not in locals() else inclusion_tags  # keep tags
        if vocabulary:
            domain_matches = self.matcher.match_vocabulary(paper, vocabulary, threshold=0.5)
            for concept, conf in domain_matches.items():
                inclusion_tags.append(
                    InclusionTag(
                        tag_id=f"vocab_{concept}",
                        tag_name=concept,
                        category="vocabulary",
                        confidence=conf,
                        source="auto",
                        reasoning=f"Domain vocabulary match: {concept}",
                    )
                )
        duration_ms = int((time.time() - start_time) * 1000)
        return ScreeningResult(
            paper_id=paper.paper_id,
            decision=decision,
            confidence=confidence,
            mode=mode,
            exclusion_reasons=exclusion_reasons,
            inclusion_tags=inclusion_tags,
            domain_matches=domain_matches,
            screening_duration_ms=duration_ms,
        )

    def screen_batch(
        self,
        papers: List[Paper],
        inclusion_criteria: List[ScreeningCriterion],
        exclusion_criteria: List[ScreeningCriterion],
        vocabulary: Optional[DomainVocabulary] = None,
        mode: ScreeningMode = ScreeningMode.AUTO,
    ) -> List[ScreeningResult]:
        """Screen a batch of papers and return their results."""
        logger.info(f"Screening {len(papers)} papers in {mode} mode")
        results: List[ScreeningResult] = []
        for i, paper in enumerate(papers, 1):
            if i % 10 == 0:
                logger.info(f"Screened {i}/{len(papers)} papers")
            result = self.screen_paper(
                paper,
                inclusion_criteria,
                exclusion_criteria,
                vocabulary,
                mode,
            )
            results.append(result)
        logger.info(
            f"Screening complete. Include={sum(1 for r in results if r.decision == ScreeningDecision.INCLUDE)}, "
            f"Exclude={sum(1 for r in results if r.decision == ScreeningDecision.EXCLUDE)}, "
            f"Maybe={sum(1 for r in results if r.decision == ScreeningDecision.MAYBE)}"
        )
        return results

    def active_learning_candidates(self, results: List[ScreeningResult], top_k: int = 20) -> List[str]:
        """Select candidate paper IDs for human review based on uncertainty."""
        candidates: List[Tuple[str, float]] = []
        for r in results:
            # Uncertainty: high when confidence near 0.5
            uncertainty = 1.0 - abs(r.confidence - 0.5) * 2
            # Maybe decisions are prioritised
            if r.decision == ScreeningDecision.MAYBE:
                uncertainty *= 1.5
            # Conflicting inclusion/exclusion evidence
            if r.inclusion_tags and r.exclusion_reasons:
                uncertainty *= 1.3
            candidates.append((r.paper_id, uncertainty))
        # Sort descending by uncertainty
        candidates.sort(key=lambda x: x[1], reverse=True)
        return [paper_id for paper_id, _ in candidates[:top_k]]