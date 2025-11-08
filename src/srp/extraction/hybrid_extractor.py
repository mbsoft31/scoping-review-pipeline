"""Hybrid data extraction with cascading strategies.

This module defines a ``HybridExtractor`` that attempts to extract
structured data from a paper using a series of increasingly
expensive methods.  First, regular expressions and simple heuristics
are applied via the existing ``DataExtractor``.  If that fails to
produce sufficiently complete results, the extractor optionally
escalates to an LLM via the ``ModelRouter``.  The goal is to avoid
using costly LLM calls unless necessary.

The implementation here is intentionally modest: it does not
integrate spaCy NER or other advanced techniques to keep the
dependencies light.  It nonetheless demonstrates how to combine
deterministic extraction with LLM‑based fallback.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..core.models import Paper
from ..llm.router import ModelRouter, TaskComplexity
from .extractor import DataExtractor
from .models import ExtractedData
from ..utils.logging import get_logger

logger = get_logger(__name__)


class HybridExtractor:
    """Data extraction using regex with optional LLM fallback."""

    def __init__(self, router: Optional[ModelRouter] = None, min_citation_for_llm: int = 50) -> None:
        self.router = router or ModelRouter()
        self.min_citation = min_citation_for_llm
        self.regex_extractor = DataExtractor()
        # Statistics counters
        self.regex_success: int = 0
        self.llm_used: int = 0
        self.fallback_used: int = 0

    async def extract_from_paper(self, paper: Paper, *, full_text: Optional[str] = None) -> ExtractedData:
        """Extract information from a paper.

        The method first uses regex heuristics.  If the extraction is
        incomplete and the paper meets the citation threshold, it
        escalates to an LLM via the router.  Finally, the regex result
        is returned if the LLM is not used or fails.
        """
        text = full_text or paper.abstract or ""
        regex_result = self._regex_extract(text)
        completeness = self._assess_completeness(regex_result)
        if completeness >= 0.6:
            self.regex_success += 1
            regex_result.paper_id = paper.paper_id
            return regex_result
        # Escalate to LLM if high‑citation paper
        if paper.citation_count >= self.min_citation:
            try:
                llm_res = await self.router.route_task(
                    task_type="extract",
                    input_data={"text": text},
                    complexity=TaskComplexity.MODERATE,
                )
                self.llm_used += 1
                extracted = self._to_extracted_data(paper.paper_id, llm_res)
                return extracted
            except Exception as exc:
                logger.warning(f"LLM extraction failed for paper {paper.paper_id}: {exc}")
        # Fallback to regex result
        self.fallback_used += 1
        regex_result.paper_id = paper.paper_id
        return regex_result

    def _regex_extract(self, text: str) -> ExtractedData:
        """Apply regex heuristics using the built‑in ``DataExtractor``."""
        sample_size = self.regex_extractor.extract_sample_size(text)
        pvalues = self.regex_extractor.extract_pvalues(text)
        effect_sizes = self.regex_extractor.extract_effect_sizes(text)
        study_design = self.regex_extractor.detect_study_design(text)
        return ExtractedData(
            paper_id="",
            study_design=study_design,
            sample_size=sample_size,
            pvalues=pvalues,
            effect_sizes=effect_sizes,
            statistical_methods=self.regex_extractor._extract_statistical_methods(text),
            extraction_confidence=0.6,
        )

    def _assess_completeness(self, extracted: ExtractedData) -> float:
        """Return a simple completeness score between 0 and 1."""
        flags = [
            extracted.study_design != "unknown",
            extracted.sample_size is not None,
            bool(extracted.pvalues) or bool(extracted.effect_sizes),
        ]
        return sum(flags) / len(flags)

    def _to_extracted_data(self, paper_id: str, res: Dict[str, any]) -> ExtractedData:
        """Convert LLM result dictionary into ``ExtractedData``."""
        return ExtractedData(
            paper_id=paper_id,
            study_design=res.get("study_design", "unknown"),
            sample_size=res.get("sample_size"),
            pvalues=res.get("pvalues", []),
            effect_sizes=res.get("effect_sizes", []),
            statistical_methods=res.get("statistical_methods", []),
            interventions=res.get("interventions", []),
            outcomes=res.get("outcomes", []),
            extraction_confidence=res.get("confidence", 0.8),
        )

    @property
    def extraction_stats(self) -> Dict[str, int]:
        """Return a dictionary summarising extraction usage."""
        return {
            "regex_success": self.regex_success,
            "llm_used": self.llm_used,
            "fallback_used": self.fallback_used,
        }