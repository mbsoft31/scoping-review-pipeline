"""Automated data extraction from full‑text papers using NLP.

This module defines classes and functions for retrieving full‑text
documents (via open access or Unpaywall) and extracting structured
information from those documents.  The extraction focuses on
elements commonly required for evidence synthesis: study design,
sample sizes, interventions and outcomes, effect sizes, p‑values,
confidence intervals and statistical methods.  Patterns are used to
detect numerical values when no dedicated NLP model is available.

The extraction functions return instances of :class:`ExtractedData`
which can be consumed by quality assessment and meta‑analysis
modules.

"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from ..core.models import Paper
from ..utils.logging import get_logger
from .models import ExtractedData, Intervention, Outcome, StudyDesignType

logger = get_logger(__name__)


@dataclass
class FullTextDocument:
    """Simple container for a full‑text paper.

    Attributes:
        paper_id: Identifier of the paper (typically a DOI‑derived ID).
        text: The raw text of the full document.
        sections: Mapping of section names to their contents.  This
            allows targeted extraction from methods, results or abstract
            sections when available.
        source: Indicates how the document was obtained (e.g. 'pdf',
            'html', 'xml').
    """

    paper_id: str
    text: str
    sections: Dict[str, str]
    source: str


class DataExtractor:
    """Extract structured data from full‑text papers.

    The extractor uses a combination of regular expression heuristics
    and keyword detection to identify key information in the full
    text.  A more sophisticated implementation could incorporate
    transformer‑based named entity recognition (NER) for improved
    accuracy.  The patterns used here are intentionally simple to
    avoid heavy dependencies while providing a reasonable baseline.
    """

    def __init__(self, model_name: str = "allenai/scibert_scivocab_uncased"):
        """Initialize the data extractor.

        Args:
            model_name: Name of a transformer model to use for NER.  At
                present this argument is unused but reserved for
                future upgrades.
        """
        self.model_name = model_name
        self._init_patterns()

    def _init_patterns(self) -> None:
        """Compile regular expression patterns used for extraction."""
        # Patterns for sample size extraction
        self.sample_patterns: List[str] = [
            r"[Nn]=?\s*(\d+)",
            r"(\d+)\s+participants?",
            r"(\d+)\s+patients?",
            r"sample\s+size\s+of\s+(\d+)",
            r"total\s+of\s+(\d+)",
        ]

        # Patterns for p‑value extraction
        self.pvalue_patterns: List[str] = [
            r"[Pp]\s*[=<>]\s*([\d.]+)",
            r"[Pp]-value\s*[=<>]\s*([\d.]+)",
        ]

        # Patterns for effect size extraction
        self.effect_patterns: List[str] = [
            r"(?:OR|RR|HR)\s*[=:]\s*([\d.]+)",
            r"(?:odds ratio|relative risk|hazard ratio)\s+of\s+([\d.]+)",
            r"Cohen\'?s?\s+d\s*[=:]\s*([\d.]+)",
            r"effect\s+size\s*[=:]\s*([\d.]+)",
        ]

        # Patterns for confidence interval extraction
        self.ci_patterns: List[str] = [
            r"95%\s*CI\s*[:\[]?\s*([\d.]+)\s*[-–to]\s*([\d.]+)",
            r"\[?([\d.]+)\s*[-–]\s*([\d.]+)\]?\s*95%\s*CI",
        ]

        # Keywords for detecting study design
        self.design_keywords: Dict[str, List[str]] = {
            "randomized controlled trial": ["randomized", "randomised", "rct"],
            "cohort study": ["cohort", "longitudinal", "prospective"],
            "case-control": ["case-control", "case control"],
            "cross-sectional": ["cross-sectional", "cross sectional", "survey"],
            "systematic review": ["systematic review", "meta-analysis"],
            "case study": ["case study", "case report"],
        }

    def extract_sample_size(self, text: str) -> Optional[int]:
        """Extract the largest sample size found in a block of text."""
        for pattern in self.sample_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                sizes = [int(m) for m in matches if isinstance(m, str) and m.isdigit()]
                if sizes:
                    return max(sizes)
        return None

    def extract_pvalues(self, text: str) -> List[float]:
        """Extract p‑values from text."""
        pvalues: List[float] = []
        for pattern in self.pvalue_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    pval = float(match)
                    if 0.0 <= pval <= 1.0:
                        pvalues.append(pval)
                except ValueError:
                    continue
        return pvalues

    def extract_effect_sizes(self, text: str) -> List[Dict[str, Any]]:
        """Extract effect sizes and associated confidence intervals."""
        effects: List[Dict[str, Any]] = []
        for pattern in self.effect_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    value = float(match.group(1))
                    # Search local context for a CI within ±50 characters
                    context = text[max(0, match.start() - 50): match.end() + 50]
                    ci = self._extract_ci_from_context(context)
                    effects.append({
                        "type": "effect_size",
                        "value": value,
                        "confidence_interval": ci,
                        "context": context.strip(),
                    })
                except (ValueError, IndexError):
                    continue
        return effects

    def _extract_ci_from_context(self, text: str) -> Optional[Tuple[float, float]]:
        """Extract a confidence interval from a short snippet of text."""
        for pattern in self.ci_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    lower = float(match.group(1))
                    upper = float(match.group(2))
                    return (lower, upper)
                except (ValueError, IndexError):
                    continue
        return None

    def detect_study_design(self, text: str) -> str:
        """Detect the study design based on keyword frequency."""
        text_lower = text.lower()
        scores: Dict[str, int] = {}
        for design, keywords in self.design_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[design] = score
        if scores:
            return max(scores, key=scores.get)
        return StudyDesignType.UNKNOWN.value

    def _extract_statistical_methods(self, text: str) -> List[str]:
        """Detect mentions of common statistical methods."""
        methods: List[str] = []
        method_keywords = {
            "t-test", "anova", "regression", "chi-square", "mann-whitney",
            "wilcoxon", "kruskal-wallis", "meta-analysis", "random effects",
            "fixed effects", "mixed models", "multilevel", "structural equation"
        }
        text_lower = text.lower()
        for method in method_keywords:
            if method.lower() in text_lower:
                methods.append(method)
        return methods

    def extract_from_sections(self, doc: FullTextDocument) -> ExtractedData:
        """Extract structured data from a document organised into sections."""
        methods_text = doc.sections.get("methods", "") + " " + doc.sections.get("methodology", "")
        results_text = doc.sections.get("results", "")
        abstract_text = doc.sections.get("abstract", "")
        # Study design detection
        study_design = self.detect_study_design(methods_text + " " + abstract_text)
        # Sample size
        sample_size = self.extract_sample_size(methods_text + " " + results_text)
        # Statistical results
        pvalues = self.extract_pvalues(results_text)
        effect_sizes = self.extract_effect_sizes(results_text)
        extracted = ExtractedData(
            paper_id=doc.paper_id,
            study_design=study_design,
            sample_size=sample_size,
            interventions=[],
            outcomes=[],
            pvalues=pvalues,
            effect_sizes=effect_sizes,
            statistical_methods=self._extract_statistical_methods(methods_text),
            extracted_at=datetime.utcnow(),
            extraction_confidence=0.0,
        )
        return extracted


class FullTextRetriever:
    """Retrieve full‑text articles from various sources.

    This class attempts to download open access PDFs or use the
    Unpaywall API as a fallback.  Parsing of PDF content into text
    should be implemented by a concrete subclass or external
    dependency (e.g. PyMuPDF).
    """

    def __init__(self, unpaywall_email: Optional[str] = None) -> None:
        self.unpaywall_email = unpaywall_email

    async def retrieve_pdf(self, paper: Paper) -> Optional[bytes]:
        """Retrieve PDF content for a paper if available."""
        # Try direct open access link first
        if getattr(paper, "open_access_pdf", None):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(paper.open_access_pdf, follow_redirects=True)
                    if response.status_code == 200:
                        return response.content
            except Exception as exc:
                logger.warning(f"Failed to retrieve OA PDF for {paper.paper_id}: {exc}")
        # Use Unpaywall if DOI and email available
        if getattr(paper, "doi", None) and self.unpaywall_email:
            try:
                unpaywall_url = f"https://api.unpaywall.org/v2/{paper.doi}?email={self.unpaywall_email}"
                async with httpx.AsyncClient() as client:
                    response = await client.get(unpaywall_url)
                    if response.status_code == 200:
                        data = response.json()
                        oa_loc = data.get("best_oa_location") or {}
                        pdf_url = oa_loc.get("url_for_pdf")
                        if pdf_url:
                            pdf_response = await client.get(pdf_url)
                            if pdf_response.status_code == 200:
                                return pdf_response.content
            except Exception as exc:
                logger.warning(f"Failed to retrieve via Unpaywall for {paper.paper_id}: {exc}")
        return None

    async def parse_pdf_to_text(self, pdf_content: bytes) -> FullTextDocument:
        """Parse PDF bytes into a ``FullTextDocument``.

        This method is a placeholder and should be overridden by a
        concrete implementation using tools such as PyMuPDF, pdfplumber
        or GROBID.  It returns an empty document by default to avoid
        runtime errors if no parser is installed.
        """
        return FullTextDocument(paper_id="unknown", text="", sections={}, source="pdf")