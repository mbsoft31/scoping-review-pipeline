"""Human‑in‑the‑loop screening queue management.

This module defines a ``HITLReviewer`` class that manages a queue of
papers requiring human review.  It stores queue and history data on
disk, supports fetching next items for review, submitting review
decisions and computing simple statistics such as agreement with
auto‑screening results.

The review queue persists between sessions, enabling collaborative
review of uncertain screening decisions.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..core.models import Paper
from .models import ScreeningResult, ScreeningDecision
from ..utils.logging import get_logger

logger = get_logger(__name__)


class HITLReviewer:
    """Manage a human review queue for screening results."""

    def __init__(self, review_dir: Path) -> None:
        self.review_dir = review_dir
        self.review_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = review_dir / "review_queue.csv"
        self.history_file = review_dir / "review_history.csv"

    def create_review_queue(
        self,
        papers: List[Paper],
        auto_results: List[ScreeningResult],
        priority_paper_ids: Optional[List[str]] = None,
    ) -> None:
        """Create a review queue for uncertain papers.

        Only papers with a ``maybe`` decision or low confidence are
        added to the queue.  Papers listed in ``priority_paper_ids``
        appear first in the queue.
        """
        results_map = {r.paper_id: r for r in auto_results}
        papers_map = {p.paper_id: p for p in papers}
        queue_items: List[Dict[str, object]] = []
        # Determine order: priority IDs first, then the rest
        ordered_ids = priority_paper_ids or list(papers_map.keys())
        for pid in ordered_ids:
            if pid not in results_map:
                continue
            paper = papers_map[pid]
            result = results_map[pid]
            # Only queue uncertain papers
            if result.decision == ScreeningDecision.MAYBE or result.confidence < 0.7:
                queue_items.append(
                    {
                        "paper_id": pid,
                        "title": paper.title,
                        "authors": "; ".join([a.name for a in paper.authors[:3]]),
                        "year": paper.year,
                        "auto_decision": result.decision.value,
                        "auto_confidence": result.confidence,
                        "exclusion_reasons": "; ".join([r.criterion_name for r in result.exclusion_reasons]),
                        "inclusion_tags": "; ".join([t.tag_name for t in result.inclusion_tags]),
                        "priority": 1 if priority_paper_ids and pid in priority_paper_ids else 0,
                        "reviewed": False,
                        "human_decision": None,
                        "reviewer": None,
                        "notes": None,
                    }
                )
        # Sort by priority then ascending confidence
        queue_items.sort(key=lambda x: (-(x["priority"]), x["auto_confidence"]))
        df = pd.DataFrame(queue_items)
        df.to_csv(self.queue_file, index=False)
        logger.info(f"Created review queue with {len(queue_items)} items")

    def get_next_for_review(self, n: int = 1) -> List[Dict[str, object]]:
        """Return the next N unreviewed queue items for review."""
        if not self.queue_file.exists():
            return []
        df = pd.read_csv(self.queue_file)
        unreviewed = df[df["reviewed"] == False]
        return unreviewed.head(n).to_dict("records")

    def submit_review(
        self,
        paper_id: str,
        decision: ScreeningDecision,
        reviewer: str,
        notes: Optional[str] = None,
    ) -> None:
        """Record a human review decision for a paper."""
        df = pd.read_csv(self.queue_file)
        mask = df["paper_id"] == paper_id
        df.loc[mask, "reviewed"] = True
        df.loc[mask, "human_decision"] = decision.value
        df.loc[mask, "reviewer"] = reviewer
        df.loc[mask, "notes"] = notes or ""
        df.to_csv(self.queue_file, index=False)
        # Append to history
        entry = {
            "paper_id": paper_id,
            "decision": decision.value,
            "reviewer": reviewer,
            "reviewed_at": datetime.utcnow().isoformat(),
            "notes": notes or "",
        }
        if self.history_file.exists():
            hist = pd.read_csv(self.history_file)
            hist = pd.concat([hist, pd.DataFrame([entry])], ignore_index=True)
        else:
            hist = pd.DataFrame([entry])
        hist.to_csv(self.history_file, index=False)
        logger.info(f"Recorded review for {paper_id}: {decision.value} by {reviewer}")

    def get_statistics(self) -> Dict[str, object]:
        """Return statistics about the review queue."""
        if not self.queue_file.exists():
            return {}
        df = pd.read_csv(self.queue_file)
        stats: Dict[str, object] = {
            "total": len(df),
            "reviewed": int(df["reviewed"].sum()),
            "remaining": int((~df["reviewed"]).sum()),
            "decisions": df[df["reviewed"] == True]["human_decision"].value_counts().to_dict(),
        }
        # Agreement rate: proportion of human decisions matching auto
        reviewed = df[df["reviewed"] == True]
        if not reviewed.empty:
            agreement = (reviewed["auto_decision"] == reviewed["human_decision"]).sum()
            stats["auto_agreement_rate"] = agreement / len(reviewed)
        return stats

    def export_final_decisions(self, output_path: Path) -> pd.DataFrame:
        """Export final decisions combining auto and human screens."""
        df = pd.read_csv(self.queue_file)
        df["final_decision"] = df["human_decision"].fillna(df["auto_decision"])
        export_df = df[[
            "paper_id",
            "title",
            "final_decision",
            "auto_decision",
            "auto_confidence",
            "human_decision",
            "reviewer",
            "notes",
        ]]
        export_df.to_csv(output_path, index=False)
        logger.info(f"Exported final decisions to {output_path}")
        return export_df