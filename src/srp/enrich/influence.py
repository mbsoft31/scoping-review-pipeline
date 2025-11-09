"""Influence scoring for academic papers based on citation networks.

This module provides functionality to construct a directed citation graph from
deduplicated papers and their resolved references, compute various centrality
measures (PageRank, in‑degree, betweenness), combine these measures into a
single influence score, and expose simple helpers to inspect graph statistics.

The influence score is a weighted combination of normalized centrality metrics
along with the log‑transformed total citation count. The default weights are
chosen to give more emphasis to network‑derived importance (PageRank and
in‑degree) but can be adjusted by the caller if desired.

Usage:
    scorer = InfluenceScorer()
    G = scorer._build_citation_graph(papers, references)
    df = scorer.compute_influence_scores(papers, references)
    stats = scorer.get_graph_statistics(G)

The resulting DataFrame contains one row per paper with its rank and individual
metric values. The graph statistics provide high‑level information about the
citation network.
"""

from __future__ import annotations

from typing import List, Dict, Tuple, Optional
import math

try:
    import networkx as nx  # type: ignore
except ImportError:  # pragma: no cover - fallback when networkx not available
    nx = None  # type: ignore

import pandas as pd  # type: ignore

from ..core.models import Paper, Reference
from ..utils.logging import get_logger


logger = get_logger(__name__)


class InfluenceScorer:
    """Compute influence scores for papers using citation network analysis."""

    def __init__(
        self,
        weight_pagerank: float = 0.4,
        weight_in_degree: float = 0.3,
        weight_betweenness: float = 0.2,
        weight_log_citations: float = 0.1,
    ) -> None:
        """
        Initialize an InfluenceScorer with configurable weights.

        Args:
            weight_pagerank: Weight for the PageRank component.
            weight_in_degree: Weight for the in‑degree component (in‑corpus citations).
            weight_betweenness: Weight for the betweenness centrality component.
            weight_log_citations: Weight for the log‑transformed total citation count.
        """
        total = weight_pagerank + weight_in_degree + weight_betweenness + weight_log_citations
        # Normalize weights to sum to 1 to avoid accidental misconfiguration
        if total > 0:
            self.weight_pagerank = weight_pagerank / total
            self.weight_in_degree = weight_in_degree / total
            self.weight_betweenness = weight_betweenness / total
            self.weight_log_citations = weight_log_citations / total
        else:
            # Fall back to equal weights
            self.weight_pagerank = self.weight_in_degree = self.weight_betweenness = self.weight_log_citations = 0.25
        logger.debug(
            "Initialized InfluenceScorer with weights: PR=%.3f, in_deg=%.3f, bet=%.3f, logC=%.3f",
            self.weight_pagerank,
            self.weight_in_degree,
            self.weight_betweenness,
            self.weight_log_citations,
        )

    def build_citation_graph(self, papers: List[Paper], references: List[Reference]) -> nx.DiGraph:
        """Construct a directed citation graph from papers and resolved references.

        Nodes correspond to paper IDs. Directed edges go from the citing paper to
        the cited paper, but only include edges where the cited paper is
        in‑corpus (i.e., has a resolved cited_paper_id). Self‑citations are
        ignored.

        Args:
            papers: List of deduplicated papers in the corpus.
            references: List of resolved references linking citing and cited papers.

        Returns:
            A directed NetworkX graph representing the citation network.
        """
        # If networkx is not available, construct a simple adjacency dict to emulate
        if nx is None:  # pragma: no cover
            # Represent graph as dict of dicts with edge weights
            G = {
                "nodes": {p.paper_id: p for p in papers},
                "edges": {},  # type: Dict[str, Dict[str, int]]
            }
            for ref in references:
                citing = ref.citing_paper_id
                cited = ref.cited_paper_id
                if citing and cited and citing != cited:
                    G["edges"].setdefault(citing, {})[cited] = G["edges"].get(citing, {}).get(cited, 0) + 1
            return G  # type: ignore
        else:
            G = nx.DiGraph()
            # Add nodes for all papers
            for paper in papers:
                G.add_node(paper.paper_id, paper=paper)
            # Add edges for in‑corpus citations
            for ref in references:
                citing = ref.citing_paper_id
                cited = ref.cited_paper_id
                if citing and cited and citing != cited:
                    # Multiple citations between the same pair are represented as
                    # multi‑edge counts on the DiGraph via edge attribute weight.
                    if G.has_edge(citing, cited):
                        G[citing][cited]["weight"] += 1
                    else:
                        G.add_edge(citing, cited, weight=1)
            logger.debug(
                "Constructed citation graph with %d nodes and %d edges",
                G.number_of_nodes(),
                G.number_of_edges(),
            )
            return G

    def _normalize_series(self, series: pd.Series) -> pd.Series:
        """Min‑max normalize a pandas Series to the [0, 1] range.

        If all values are identical, returns a series of zeros to avoid division
        by zero. NaN values are treated as zeros.

        Args:
            series: Series of numeric values.

        Returns:
            Normalized series.
        """
        values = series.fillna(0).astype(float)
        min_val = values.min()
        max_val = values.max()
        if max_val > min_val:
            return (values - min_val) / (max_val - min_val)
        else:
            # All values identical; return zeros
            return pd.Series([0.0] * len(values), index=series.index)

    def compute_influence_scores(self, papers: List[Paper], references: List[Reference]) -> pd.DataFrame:
        """Compute influence scores for each paper.

        Constructs the citation graph, computes centrality measures, normalizes
        them, combines them into a single influence score according to the
        configured weights, sorts the papers by influence score, and returns a
        DataFrame with results.

        Args:
            papers: Deduplicated list of papers.
            references: List of resolved references (with cited_paper_id filled where
                possible).

        Returns:
            pandas.DataFrame: Rows for each paper with columns:
                paper_id, title, year, doi, total_citations, corpus_in_degree,
                pagerank, betweenness, influence_score, rank.
        """
        logger.info("Building citation graph for influence scoring")
        G = self.build_citation_graph(papers, references)
        # Compute PageRank, in-degree and betweenness. If networkx is unavailable,
        # use simple fallbacks.
        if nx is None:  # pragma: no cover
            # Fallback PageRank and betweenness: use in-degree proportions
            total_edges = 0
            in_deg_fallback: Dict[str, int] = {}
            for citing, targets in G["edges"].items():  # type: ignore
                for cited, weight in targets.items():
                    in_deg_fallback[cited] = in_deg_fallback.get(cited, 0) + weight
                    total_edges += weight
            # Ensure all nodes present
            for p in papers:
                in_deg_fallback.setdefault(p.paper_id, 0)
            pagerank_scores = {
                node: (in_deg_fallback[node] / total_edges if total_edges > 0 else 0)
                for node in G["nodes"].keys()
            }
            betweenness = {node: 0.0 for node in G["nodes"].keys()}
            in_deg = in_deg_fallback  # assign to common variable
        else:
            # Compute PageRank. Use edge weights if available; fall back to unweighted.
            try:
                pagerank_scores = nx.pagerank(G, weight="weight")
            except Exception as e:
                logger.warning(f"PageRank computation failed: {e}")
                total_edges = G.number_of_edges()
                pagerank_scores = {node: (G.in_degree(node) / total_edges if total_edges > 0 else 0) for node in G.nodes()}
            # Compute in-degree (number of in‑corpus citations)
            in_deg = dict(G.in_degree())
            # Compute betweenness centrality. Use normalized betweenness for directed graphs.
            try:
                betweenness = nx.betweenness_centrality(G, normalized=True, weight="weight", endpoints=False)
            except Exception as e:
                logger.warning(f"Betweenness centrality computation failed: {e}")
                betweenness = {node: 0.0 for node in G.nodes()}
        # Build DataFrame with metrics
        records: List[Dict[str, object]] = []
        for p in papers:
            pr = pagerank_scores.get(p.paper_id, 0.0)
            indeg = in_deg.get(p.paper_id, 0)
            btw = betweenness.get(p.paper_id, 0.0)
            total_cites = p.citation_count or 0
            log_cites = math.log1p(total_cites)
            records.append(
                {
                    "paper_id": p.paper_id,
                    "title": p.title,
                    "year": p.year,
                    "doi": p.doi,
                    "total_citations": total_cites,
                    "corpus_in_degree": indeg,
                    "pagerank": pr,
                    "betweenness": btw,
                    "log_citations": log_cites,
                }
            )
        df = pd.DataFrame(records)
        # Normalize metrics
        df["norm_pagerank"] = self._normalize_series(df["pagerank"])
        df["norm_in_degree"] = self._normalize_series(df["corpus_in_degree"].astype(float))
        df["norm_betweenness"] = self._normalize_series(df["betweenness"])
        df["norm_log_cites"] = self._normalize_series(df["log_citations"])
        # Compute influence score
        df["influence_score"] = (
            self.weight_pagerank * df["norm_pagerank"]
            + self.weight_in_degree * df["norm_in_degree"]
            + self.weight_betweenness * df["norm_betweenness"]
            + self.weight_log_citations * df["norm_log_cites"]
        )
        # Rank papers descending by influence score
        df = df.sort_values(by="influence_score", ascending=False).reset_index(drop=True)
        df["rank"] = df.index + 1
        # Drop intermediate normalized columns for clarity
        return df[
            [
                "rank",
                "paper_id",
                "title",
                "year",
                "doi",
                "total_citations",
                "corpus_in_degree",
                "pagerank",
                "betweenness",
                "influence_score",
            ]
        ]

    def get_graph_statistics(self, G: nx.DiGraph) -> Dict[str, float]:
        """Compute simple statistics of the citation graph.

        Args:
            G: A directed citation graph.

        Returns:
            Dictionary with graph statistics including number of nodes, number of
            edges, density, average in‑degree, average out‑degree, and the
            fraction of isolated nodes.
        """
        n = G.number_of_nodes()
        m = G.number_of_edges()
        density = nx.density(G) if n > 1 else 0.0
        # Average degrees
        avg_in = sum(dict(G.in_degree()).values()) / n if n > 0 else 0.0
        avg_out = sum(dict(G.out_degree()).values()) / n if n > 0 else 0.0
        isolated = sum(1 for node in G.nodes() if G.degree(node) == 0)
        frac_isolated = isolated / n if n > 0 else 0.0
        return {
            "num_nodes": n,
            "num_edges": m,
            "density": density,
            "avg_in_degree": avg_in,
            "avg_out_degree": avg_out,
            "isolated_fraction": frac_isolated,
        }