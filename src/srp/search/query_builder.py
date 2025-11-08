"""Systematic query generation for comprehensive literature coverage."""

from typing import List, Set, Dict, Optional
from itertools import combinations
import yaml
from pathlib import Path

from ..config.settings import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class QueryBuilder:
    """
    Generate systematic queries for literature reviews.

    Strategies:
    - Core term pairs for breadth
    - Method/technique augmentation for depth
    - Context-specific variations
    - Source-specific optimization (e.g., shorter for S2)
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Optional[Path]) -> dict:
        if config_path and config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {
            "core_terms": [],
            "method_terms": [],
            "context_terms": [],
            "boolean_operators": ["AND", "OR"],
            "max_terms_per_query": 5,
        }

    def generate_core_pairs(self, terms: List[str]) -> List[str]:
        queries: List[str] = []
        for term1, term2 in combinations(terms, 2):
            queries.append(f"{term1} {term2}")
        return queries

    def generate_augmented_queries(
        self,
        core_queries: List[str],
        augmentation_terms: List[str],
        max_augmentations: int = 2,
    ) -> List[str]:
        queries: List[str] = []
        for core in core_queries:
            queries.append(core)
            # Skip augmentation if no terms provided
            if not augmentation_terms:
                continue
            for aug_combo in combinations(augmentation_terms, min(max_augmentations, len(augmentation_terms))):
                if aug_combo:  # Only add if there are actual augmentation terms
                    augmented = f"{core} {' '.join(aug_combo)}"
                    queries.append(augmented)
        return queries

    def optimize_for_source(self, query: str, source: str) -> str:
        if source == "semantic_scholar":
            terms = query.split()
            if len(terms) > 4:
                return " ".join(terms[:4])
        # For other sources we keep as is for now
        return query

    def generate_systematic_queries(
        self,
        core_terms: List[str],
        method_terms: Optional[List[str]] = None,
        context_terms: Optional[List[str]] = None,
        include_augmented: bool = True,
    ) -> List[str]:
        queries: Set[str] = set()
        core_queries = self.generate_core_pairs(core_terms)
        queries.update(core_queries)
        logger.info(f"Generated {len(core_queries)} core pair queries")
        if include_augmented:
            if method_terms:
                method_augmented = self.generate_augmented_queries(core_queries, method_terms, max_augmentations=2)
                queries.update(method_augmented)
                logger.info(f"Added {len(method_augmented)} method-augmented queries")
            if context_terms:
                context_augmented = self.generate_augmented_queries(core_queries, context_terms, max_augmentations=2)
                queries.update(context_augmented)
                logger.info(f"Added {len(context_augmented)} context-augmented queries")
        query_list = sorted(list(queries))
        logger.info(f"Total queries generated: {len(query_list)}")
        return query_list

    def save_queries(self, queries: List[str], output_path: Path) -> None:
        with open(output_path, "w") as f:
            f.write("# Generated Search Queries\n\n")
            f.write(f"Total queries: {len(queries)}\n\n")
            for i, query in enumerate(queries, 1):
                f.write(f"{i}. `{query}`\n")
        logger.info(f"Saved {len(queries)} queries to {output_path}")


def load_domain_terms(domain: str) -> Dict[str, List[str]]:
    domains: Dict[str, Dict[str, List[str]]] = {
        "ai_bias": {
            "core": [
                "artificial intelligence",
                "machine learning",
                "algorithmic bias",
                "fairness",
                "discrimination",
                "equity",
            ],
            "method": [
                "detection",
                "mitigation",
                "measurement",
                "evaluation",
                "testing",
            ],
            "context": [
                "hiring",
                "criminal justice",
                "healthcare",
                "education",
                "finance",
            ],
        },
        "climate_adaptation": {
            "core": [
                "climate change",
                "adaptation",
                "resilience",
                "vulnerability",
                "mitigation",
            ],
            "method": [
                "modeling",
                "assessment",
                "planning",
                "policy",
            ],
            "context": [
                "urban",
                "coastal",
                "agriculture",
                "infrastructure",
            ],
        },
    }
    return domains.get(domain, {"core": [], "method": [], "context": []})