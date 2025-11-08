"""Risk‑of‑bias assessment using standard tools.

This module implements a heuristic risk‑of‑bias assessor that scans
available text for keywords indicative of adequate or inadequate
methods.  It supports several well‑known tools, including Cochrane
RoB 2 and Newcastle–Ottawa, and produces structured judgments
describing the level of concern for each domain as well as an
overall rating.  While automated, this approach can provide a
starting point for human reviewers and highlight studies needing
additional scrutiny.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from ..core.models import Paper
from ..extraction.models import ExtractedData
from ..utils.logging import get_logger
from .models import BiasJudgment, RiskOfBiasAssessment

logger = get_logger(__name__)


class RoBTool(str, Enum):
    """Enumeration of supported risk‑of‑bias assessment tools."""

    ROB2 = "rob2"  # Cochrane RoB 2 for randomized controlled trials
    ROBINS_I = "robins_i"  # Risk of Bias in Non‑randomized Studies of Interventions
    NEWCASTLE_OTTAWA = "newcastle_ottawa"  # For cohort/case‑control studies
    CASP = "casp"  # Critical Appraisal Skills Programme checklists
    QUADAS_C = "quadas_c"  # Diagnostic test accuracy


class RoBAssessor:
    """Perform a heuristic risk‑of‑bias assessment on a paper."""

    def __init__(self, tool: RoBTool = RoBTool.ROB2) -> None:
        self.tool = tool
        self.criteria = self._load_criteria(tool)

    def _load_criteria(self, tool: RoBTool) -> List[Dict]:
        """Load domain criteria for the specified RoB tool."""
        if tool == RoBTool.ROB2:
            return [
                {
                    "domain": "randomization",
                    "keywords": ["random", "randomized", "randomised", "computer-generated"],
                    "weight": 1.0,
                },
                {
                    "domain": "allocation_concealment",
                    "keywords": ["concealed", "sealed envelope", "central allocation"],
                    "weight": 1.0,
                },
                {
                    "domain": "blinding_participants",
                    "keywords": ["double-blind", "participant-blind", "masked"],
                    "weight": 0.8,
                },
                {
                    "domain": "blinding_assessors",
                    "keywords": ["assessor-blind", "outcome-blind", "independent assessor"],
                    "weight": 0.9,
                },
                {
                    "domain": "incomplete_data",
                    "keywords": ["intention-to-treat", "itt", "complete data", "no dropout"],
                    "weight": 0.8,
                },
                {
                    "domain": "selective_reporting",
                    "keywords": ["all outcomes", "pre-registered", "protocol"],
                    "weight": 0.9,
                },
            ]
        elif tool == RoBTool.NEWCASTLE_OTTAWA:
            return [
                {
                    "domain": "selection",
                    "keywords": ["representative", "consecutive", "population-based"],
                    "weight": 1.0,
                },
                {
                    "domain": "selection",
                    "keywords": ["same population", "matched controls"],
                    "weight": 1.0,
                },
                {
                    "domain": "comparability",
                    "keywords": ["adjusted for", "matched", "controlled for"],
                    "weight": 1.0,
                },
                {
                    "domain": "outcome",
                    "keywords": ["independent", "blind", "validated"],
                    "weight": 0.9,
                },
            ]
        else:
            # Minimal criteria for unsupported tools
            return []

    def assess_paper(
        self,
        paper: Paper,
        extracted_data: Optional[ExtractedData] = None,
        full_text: Optional[str] = None,
    ) -> RiskOfBiasAssessment:
        """Assess the risk of bias for a single paper.

        Args:
            paper: The paper being evaluated.
            extracted_data: Structured data from the full text (optional).
            full_text: The full‑text content (optional; falls back to
                paper abstract if not provided).

        Returns:
            A :class:`RiskOfBiasAssessment` describing domain judgments
            and overall risk.
        """
        text = (full_text or paper.abstract or "").lower()
        domain_judgments = []
        for criterion in self.criteria:
            # Count keyword matches
            keyword_matches = sum(1 for kw in criterion["keywords"] if kw.lower() in text)
            # Assign heuristic judgment based on number of matches
            if keyword_matches >= 2:
                judgment = BiasJudgment.LOW
                confidence = 0.7
            elif keyword_matches == 1:
                judgment = BiasJudgment.SOME_CONCERNS
                confidence = 0.5
            else:
                judgment = BiasJudgment.HIGH
                confidence = 0.3
            # Use extracted data to override certain domains
            if extracted_data:
                if criterion["domain"] == "randomization" and extracted_data.randomization_method:
                    judgment = BiasJudgment.LOW
                    confidence = 0.9
            domain_judgments.append({
                "domain": criterion["domain"],
                "judgment": judgment,
                "confidence": confidence,
                "support": f"Found {keyword_matches} relevant keywords",
            })
        # Determine overall judgment (worst domain wins)
        judgments = [d["judgment"] for d in domain_judgments]
        if BiasJudgment.HIGH in judgments:
            overall = BiasJudgment.HIGH
        elif BiasJudgment.SOME_CONCERNS in judgments:
            overall = BiasJudgment.SOME_CONCERNS
        else:
            overall = BiasJudgment.LOW
        avg_confidence = sum(d["confidence"] for d in domain_judgments) / len(domain_judgments) if domain_judgments else 0.0
        assessment = RiskOfBiasAssessment(
            paper_id=paper.paper_id,
            tool=self.tool.value,
            overall_judgment=overall,
            overall_confidence=avg_confidence,
            domain_assessments=domain_judgments,
            requires_human_review=avg_confidence < 0.6 or overall == BiasJudgment.HIGH,
        )
        return assessment