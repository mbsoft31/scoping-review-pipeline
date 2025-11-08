"""Active learning module for iterative screening.

This component implements an active learning workflow that learns
from human screening decisions and iteratively selects the most
uncertain papers for review.  It uses TF‑IDF features and a
calibrated RandomForest classifier to predict inclusion/exclusion
decisions.  The model updates as new labels are provided and
provides feature importance scores for interpretability.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer

from ..core.models import Paper
from .models import ScreeningDecision
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ActiveScreener:
    """Active learning screener that iteratively trains on labelled data."""

    def __init__(self, seed_size: int = 50) -> None:
        self.seed_size = seed_size
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 3),
            stop_words="english",
        )
        self.classifier = CalibratedClassifierCV(
            RandomForestClassifier(n_estimators=100, random_state=42),
            cv=5,
        )
        self._is_trained = False

    def prepare_features(self, papers: List[Paper]) -> np.ndarray:
        """Convert paper titles and abstracts into numerical features."""
        texts = [f"{p.title} {p.abstract or ''}" for p in papers]
        if not self._is_trained:
            features = self.vectorizer.fit_transform(texts)
        else:
            features = self.vectorizer.transform(texts)
        return features.toarray()

    def train(self, papers: List[Paper], labels: List[ScreeningDecision]) -> None:
        """Train the classifier on a set of labelled papers."""
        binary_labels: List[int] = []
        valid_papers: List[Paper] = []
        for paper, decision in zip(papers, labels):
            if decision in (ScreeningDecision.INCLUDE, ScreeningDecision.EXCLUDE):
                binary_labels.append(1 if decision == ScreeningDecision.INCLUDE else 0)
                valid_papers.append(paper)
        if len(binary_labels) < 10:
            logger.warning(f"Only {len(binary_labels)} labelled papers; need at least 10 to train")
            return
        X = self.prepare_features(valid_papers)
        y = np.array(binary_labels)
        self.classifier.fit(X, y)
        self._is_trained = True
        logger.info(f"Trained classifier on {len(binary_labels)} papers")

    def predict_batch(self, papers: List[Paper]) -> List[Tuple[ScreeningDecision, float]]:
        """Predict screening decisions for a batch of papers."""
        if not self._is_trained:
            raise ValueError("Classifier has not been trained yet")
        X = self.prepare_features(papers)
        probas = self.classifier.predict_proba(X)
        predictions: List[Tuple[ScreeningDecision, float]] = []
        for proba in probas:
            include_prob = proba[1]
            if include_prob >= 0.7:
                decision = ScreeningDecision.INCLUDE
                confidence = include_prob
            elif include_prob <= 0.3:
                decision = ScreeningDecision.EXCLUDE
                confidence = 1.0 - include_prob
            else:
                decision = ScreeningDecision.MAYBE
                confidence = 0.5
            predictions.append((decision, float(confidence)))
        return predictions

    def select_uncertain(self, papers: List[Paper], n: int = 20) -> List[Tuple[Paper, float]]:
        """Select the most uncertain papers for human review."""
        if not self._is_trained:
            raise ValueError("Classifier has not been trained yet")
        X = self.prepare_features(papers)
        probas = self.classifier.predict_proba(X)
        uncertainties: List[Tuple[Paper, float]] = []
        for i, proba in enumerate(probas):
            # Use entropy as uncertainty measure
            entropy = -np.sum(proba * np.log(proba + 1e-10))
            uncertainties.append((papers[i], float(entropy)))
        uncertainties.sort(key=lambda x: x[1], reverse=True)
        return uncertainties[:n]

    def get_feature_importance(self, top_k: int = 20) -> List[Tuple[str, float]]:
        """Return the most important TF‑IDF features used by the classifier."""
        if not self._is_trained:
            return []
        feature_names = self.vectorizer.get_feature_names_out()
        base_clf = self.classifier.calibrated_classifiers_[0].estimator
        importances = base_clf.feature_importances_
        indices = np.argsort(importances)[::-1][:top_k]
        return [(feature_names[i], float(importances[i])) for i in indices]