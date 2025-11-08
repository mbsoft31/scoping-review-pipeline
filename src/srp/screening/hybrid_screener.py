"""Hybrid screener integrating local and API models.

This module provides a simplified implementation of a hybrid screener
that delegates classification tasks to a ``ModelRouter``.  The
``HybridScreener`` accepts a paper and returns a ``ScreeningResult``
containing the decision (include, exclude or maybe) and confidence.
The intention is to perform as much work locally as possible and
escalate to API models only when the local model is not confident
enough.

The current implementation does not include active learning or
fine‑tuning; those can be added on top of this scaffold.  This file
also does not attempt to parse complex reasoning returned by API
models – the reasoning is stored as a raw string in the metadata.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional
import time

from ..core.models import Paper
from ..llm.router import ModelRouter, TaskComplexity
from ..screening.models import (
    ExclusionReason,
    InclusionTag,
    ScreeningCriterion,
    ScreeningDecision,
    ScreeningMode,
    ScreeningResult,
)
from ..utils.logging import get_logger


logger = get_logger(__name__)


class HybridScreener:
    """Hybrid screener that routes screening tasks through an LLM router."""

    def __init__(
        self,
        router: Optional[ModelRouter] = None,
        local_threshold: float = 0.7,
    ) -> None:
        self.router = router or ModelRouter(local_threshold=local_threshold)
        self.local_threshold = local_threshold
        # Statistics
        self.total_screened = 0
        self.auto_included = 0
        self.auto_excluded = 0
        self.needs_review = 0

    async def screen_paper(
        self,
        paper: Paper,
        inclusion_criteria: List[ScreeningCriterion],
        exclusion_criteria: List[ScreeningCriterion],
        *,
        mode: ScreeningMode = ScreeningMode.SEMI_AUTO,
    ) -> ScreeningResult:
        """Screen a single paper using the router.

        The paper's title and abstract are concatenated and passed to
        the router along with the inclusion/exclusion criteria.  The
        router returns a decision and confidence.  A ``ScreeningResult``
        is constructed from the output.
        """
        start = time.time()
        text = f"{paper.title}\n\n{paper.abstract or ''}"
        # Build criteria dict for the model
        criteria_dict: Dict[str, List[Dict[str, str]]] = {
            "inclusion": [
                {
                    "id": c.criterion_id,
                    "name": c.name,
                    "description": c.description,
                    "query": c.semantic_query or "",
                }
                for c in inclusion_criteria
            ],
            "exclusion": [
                {
                    "id": c.criterion_id,
                    "name": c.name,
                    "description": c.description,
                    "query": c.semantic_query or "",
                }
                for c in exclusion_criteria
            ],
        }
        # Route the task
        result = await self.router.route_task(
            task_type="classify",
            input_data={"text": text, "criteria": criteria_dict},
            complexity=TaskComplexity.MODERATE,
        )
        # Parse decision
        decision_str = result.get("decision", "maybe").lower()
        try:
            decision = ScreeningDecision(decision_str)
        except Exception:
            decision = ScreeningDecision.MAYBE
        confidence = float(result.get("confidence", 0.0))
        # Build reasons and tags (not parsed in this stub)
        reasons: List[ExclusionReason] = []
        tags: List[InclusionTag] = []
        # Determine if human review needed
        needs_review = confidence < self.local_threshold or decision == ScreeningDecision.MAYBE
        # Update stats
        self.total_screened += 1
        if not needs_review:
            if decision == ScreeningDecision.INCLUDE:
                self.auto_included += 1
            elif decision == ScreeningDecision.EXCLUDE:
                self.auto_excluded += 1
        else:
            self.needs_review += 1
        duration_ms = int((time.time() - start) * 1000)
        screening_result = ScreeningResult(
            paper_id=paper.paper_id,
            decision=decision,
            confidence=confidence,
            mode=mode,
            exclusion_reasons=reasons,
            inclusion_tags=tags,
            screening_duration_ms=duration_ms,
        )
        screening_result.metadata = {
            "tier_used": result.get("tier_used", "unknown"),
            "cost": result.get("cost", 0.0),
            "needs_review": needs_review,
            "raw_reasoning": result.get("reasoning", ""),
        }
        return screening_result

    async def screen_batch(
        self,
        papers: List[Paper],
        inclusion_criteria: List[ScreeningCriterion],
        exclusion_criteria: List[ScreeningCriterion],
        *,
        mode: ScreeningMode = ScreeningMode.SEMI_AUTO,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> List[ScreeningResult]:
        """Screen a batch of papers.

        Iterates through the papers and calls ``screen_paper`` on each.
        A progress callback may be provided to report progress.
        """
        results: List[ScreeningResult] = []
        total = len(papers)
        for idx, paper in enumerate(papers, 1):
            try:
                res = await self.screen_paper(
                    paper,
                    inclusion_criteria,
                    exclusion_criteria,
                    mode=mode,
                )
                results.append(res)
            except Exception as exc:
                logger.error(f"Failed to screen paper {paper.paper_id}: {exc}")
                results.append(
                    ScreeningResult(
                        paper_id=paper.paper_id,
                        decision=ScreeningDecision.MAYBE,
                        confidence=0.0,
                        mode=mode,
                        metadata={"error": str(exc)},
                    )
                )
            if progress_callback:
                progress_callback(idx, total)
        return results

    def get_stats(self) -> Dict[str, int]:
        """Return a summary of screening statistics."""
        return {
            "total_screened": self.total_screened,
            "auto_included": self.auto_included,
            "auto_excluded": self.auto_excluded,
            "needs_review": self.needs_review,
        }