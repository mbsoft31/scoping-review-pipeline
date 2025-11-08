"""Semantic matching utilities for screening.

This module wraps a sentence transformer model to embed text and
compute semantic similarities between paper content and criteria or
domain concepts.  It provides helper methods to extract evidence
snippets and to match against a domain vocabulary.

The default model is ``all-MiniLM-L6-v2`` which offers a good
balance between speed and quality.  If GPU support is available,
PyTorch will automatically use it.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch

from ..core.models import Paper
from .models import ScreeningCriterion, DomainVocabulary
from ..utils.logging import get_logger

logger = get_logger(__name__)


class SemanticMatcher:
    """Wrapper around a sentence transformer for semantic matching."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: Optional[str] = None) -> None:
        # Determine device: GPU if available, else CPU
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Loading semantic model: {model_name} on {self.device}")
        # Load model
        self.model = SentenceTransformer(model_name, device=self.device)
        # Simple cache to avoid recomputing embeddings
        self._embedding_cache: Dict[str, np.ndarray] = {}

    def embed_text(self, text: str) -> np.ndarray:
        """Return embedding for a single piece of text."""
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        embedding = self.model.encode(text, convert_to_tensor=False)
        self._embedding_cache[text] = embedding
        return embedding

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Return embeddings for a list of texts."""
        return self.model.encode(texts, convert_to_tensor=False, show_progress_bar=False)

    def compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two pieces of text."""
        emb1 = self.embed_text(text1)
        emb2 = self.embed_text(text2)
        sim = util.cos_sim(emb1, emb2).item()
        return float(sim)

    def match_criterion(
        self,
        paper: Paper,
        criterion: ScreeningCriterion,
        threshold: float = 0.6,
    ) -> Tuple[bool, float, List[str]]:
        """Check whether a paper matches a criterion using semantic similarity.

        Returns a tuple of (matches, confidence, evidence_snippets).
        """
        # Combine title and abstract
        paper_text = f"{paper.title}. {paper.abstract or ''}"
        # Determine similarity: use semantic_query if provided, otherwise keywords
        if criterion.semantic_query:
            sim = self.compute_similarity(paper_text, criterion.semantic_query)
        else:
            keyword_sims = [self.compute_similarity(paper_text, kw) for kw in criterion.keywords]
            sim = max(keyword_sims) if keyword_sims else 0.0
        matches = sim >= threshold
        evidence = self._extract_evidence(
            paper_text, criterion.semantic_query or " ".join(criterion.keywords), top_k=3
        )
        return matches, float(sim), evidence

    def _extract_evidence(self, text: str, query: str, top_k: int = 3) -> List[str]:
        """Extract the most relevant sentences from a paper for a given query."""
        # Very simple sentence splitting on full stops
        sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 20]
        if not sentences:
            return []
        # Compute similarity between query and each sentence
        query_emb = self.embed_text(query)
        sent_embs = self.embed_texts(sentences)
        sims = util.cos_sim(query_emb, sent_embs)[0]
        # Top k sentence indices
        top_indices = torch.topk(sims, min(top_k, len(sentences))).indices
        return [sentences[i] for i in top_indices]

    def match_vocabulary(
        self,
        paper: Paper,
        vocabulary: DomainVocabulary,
        threshold: float = 0.5,
    ) -> Dict[str, float]:
        """Match a paper against each concept in a domain vocabulary.

        Returns a mapping of concept to confidence score for concepts
        exceeding the similarity threshold.
        """
        paper_text = f"{paper.title}. {paper.abstract or ''}"
        paper_emb = self.embed_text(paper_text)
        matches: Dict[str, float] = {}
        for concept in vocabulary.concepts:
            concept_emb = self.embed_text(concept)
            sim = util.cos_sim(paper_emb, concept_emb).item()
            # Consider synonyms if available
            if concept in vocabulary.synonyms:
                syn_sims: List[float] = []
                for syn in vocabulary.synonyms[concept]:
                    syn_emb = self.embed_text(syn)
                    syn_sims.append(util.cos_sim(paper_emb, syn_emb).item())
                if syn_sims:
                    sim = max(sim, max(syn_sims))
            if sim >= threshold:
                matches[concept] = float(sim)
        return matches

    def find_similar_papers(
        self,
        target_paper: Paper,
        candidate_papers: List[Paper],
        top_k: int = 10,
    ) -> List[Tuple[Paper, float]]:
        """Return the top K most similar papers to the target paper."""
        target_text = f"{target_paper.title}. {target_paper.abstract or ''}"
        target_emb = self.embed_text(target_text)
        # Compute embeddings for candidates
        candidate_texts = [f"{p.title}. {p.abstract or ''}" for p in candidate_papers]
        candidate_embs = self.embed_texts(candidate_texts)
        sims = util.cos_sim(target_emb, candidate_embs)[0]
        top_indices = torch.topk(sims, min(top_k, len(candidate_papers))).indices
        return [(candidate_papers[i], float(sims[i])) for i in top_indices]