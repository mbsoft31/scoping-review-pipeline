"""Statistical meta‑analysis and synthesis.

This module defines the :class:`MetaAnalyzer` class for performing
basic meta‑analytic computations on a collection of effect sizes.
Functions support both fixed effect and random effects models,
heterogeneity assessment, publication bias tests (e.g. Egger's test)
and generation of data frames suitable for forest plot visualisation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats

from ..extraction.models import ExtractedData, Outcome  # noqa: F401
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EffectSize:
    """Representation of an effect size with its standard error and weight."""

    study_id: str
    effect: float
    se: float
    ci_lower: float
    ci_upper: float
    weight: float
    sample_size: Optional[int] = None


class MetaAnalyzer:
    """Perform meta‑analysis on a set of effect sizes.

    The analyser implements both fixed effect and random effects
    models using the DerSimonian–Laird estimator for between‑study
    variance.  It also provides methods for assessing heterogeneity
    and publication bias.
    """

    def compute_pooled_effect(
        self,
        effect_sizes: List[EffectSize],
        method: str = "random",
    ) -> Dict:
        """Compute the pooled effect size across a set of studies.

        Args:
            effect_sizes: List of individual study effect sizes.
            method: Either ``'fixed'`` or ``'random'`` to select the
                pooling approach.

        Returns:
            A dictionary containing the pooled estimate, its standard
            error, confidence interval, z‑score and p‑value, along
            with metadata.
        """
        if not effect_sizes:
            raise ValueError("No effect sizes provided")
        effects = np.array([es.effect for es in effect_sizes])
        ses = np.array([es.se for es in effect_sizes])
        weights = 1.0 / (ses ** 2)
        if method == "random":
            tau_squared = self._estimate_tau_squared(effects, ses, weights)
            weights = 1.0 / (ses ** 2 + tau_squared)
        pooled_effect = np.sum(weights * effects) / np.sum(weights)
        pooled_se = np.sqrt(1.0 / np.sum(weights))
        z_crit = 1.96
        ci_lower = pooled_effect - z_crit * pooled_se
        ci_upper = pooled_effect + z_crit * pooled_se
        z_score = pooled_effect / pooled_se if pooled_se > 0 else 0.0
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
        return {
            "pooled_effect": float(pooled_effect),
            "standard_error": float(pooled_se),
            "ci_lower": float(ci_lower),
            "ci_upper": float(ci_upper),
            "z_score": float(z_score),
            "p_value": float(p_value),
            "method": method,
            "n_studies": len(effect_sizes),
        }

    def _estimate_tau_squared(
        self,
        effects: np.ndarray,
        ses: np.ndarray,
        weights: np.ndarray,
    ) -> float:
        """Estimate between‑study variance (tau²) using DerSimonian–Laird."""
        k = len(effects)
        pooled = np.sum(weights * effects) / np.sum(weights)
        Q = np.sum(weights * (effects - pooled) ** 2)
        df = k - 1
        c = np.sum(weights) - np.sum(weights ** 2) / np.sum(weights)
        tau_squared = max(0.0, (Q - df) / c) if c > 0 else 0.0
        return float(tau_squared)

    def assess_heterogeneity(self, effect_sizes: List[EffectSize]) -> Dict:
        """Compute heterogeneity statistics (Q, I², tau²)."""
        effects = np.array([es.effect for es in effect_sizes])
        ses = np.array([es.se for es in effect_sizes])
        weights = 1.0 / (ses ** 2)
        k = len(effects)
        pooled = np.sum(weights * effects) / np.sum(weights)
        Q = np.sum(weights * (effects - pooled) ** 2)
        df = k - 1
        Q_pvalue = 1 - stats.chi2.cdf(Q, df) if df > 0 else 1.0
        I_squared = max(0.0, 100.0 * (Q - df) / Q) if Q > 0 else 0.0
        tau_squared = self._estimate_tau_squared(effects, ses, weights)
        if I_squared < 25:
            interpretation = "low heterogeneity"
        elif I_squared < 50:
            interpretation = "moderate heterogeneity"
        elif I_squared < 75:
            interpretation = "substantial heterogeneity"
        else:
            interpretation = "considerable heterogeneity"
        return {
            "Q": float(Q),
            "Q_df": int(df),
            "Q_pvalue": float(Q_pvalue),
            "I_squared": float(I_squared),
            "tau_squared": float(tau_squared),
            "interpretation": interpretation,
        }

    def publication_bias_test(self, effect_sizes: List[EffectSize]) -> Dict:
        """Assess publication bias using Egger's regression test."""
        if len(effect_sizes) < 3:
            return {"error": "Need at least 3 studies for Egger's test"}
        effects = np.array([es.effect for es in effect_sizes])
        ses = np.array([es.se for es in effect_sizes])
        precision = 1.0 / ses
        slope, intercept, r_value, p_value, std_err = stats.linregress(precision, effects)
        bias_detected = p_value < 0.10
        return {
            "intercept": float(intercept),
            "p_value": float(p_value),
            "bias_detected": bool(bias_detected),
            "interpretation": "Possible publication bias" if bias_detected else "No strong evidence of bias",
        }

    def generate_forest_plot_data(self, effect_sizes: List[EffectSize], pooled: Dict) -> pd.DataFrame:
        """Create a DataFrame for forest plot visualisation."""
        rows = []
        for es in effect_sizes:
            rows.append({
                "study": es.study_id,
                "effect": es.effect,
                "ci_lower": es.ci_lower,
                "ci_upper": es.ci_upper,
                "weight": es.weight,
                "type": "study",
            })
        rows.append({
            "study": "Pooled",
            "effect": pooled.get("pooled_effect"),
            "ci_lower": pooled.get("ci_lower"),
            "ci_upper": pooled.get("ci_upper"),
            "weight": None,
            "type": "pooled",
        })
        return pd.DataFrame(rows)