"""PRISMA flow diagram generation.

This module provides utilities to compute key counts from the
pipeline outputs and to draw a PRISMA flow diagram using
matplotlib.  A PRISMA flow chart depicts how many records were
identified by the search, how many duplicates were removed, how
many records were screened and excluded, how many full‑text
articles were assessed for eligibility, and how many studies were
ultimately included in the synthesis【225382337630412†L123-L187】.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Arrow
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from ..utils.logging import get_logger

logger = get_logger(__name__)


def compute_prisma_counts(
    phase1_dir: Path,
    screening_dir: Optional[Path] = None,
    dedup_dir: Optional[Path] = None,
) -> Dict[str, int]:
    """Compute counts for a PRISMA diagram from pipeline outputs.

    Args:
        phase1_dir: Directory containing Phase 1 search results (parquet/csv)
        screening_dir: Directory with screening results (optional)
        dedup_dir: Directory with deduplication results (optional)

    Returns:
        Dictionary with PRISMA counts.  Keys include:
            - records_identified: total records from search
            - duplicates_removed: number of duplicates removed (0 if none)
            - records_screened: number of records screened
            - records_excluded: number of records excluded after screening
            - reports_assessed: number of reports assessed for eligibility
            - reports_excluded: number of reports excluded after assessment
            - studies_included: number of studies included in qualitative synthesis
    """
    counts: Dict[str, int] = {
        "records_identified": 0,
        "duplicates_removed": 0,
        "records_screened": 0,
        "records_excluded": 0,
        "reports_assessed": 0,
        "reports_excluded": 0,
        "studies_included": 0,
    }
    # Phase 1: number of search results
    try:
        search_path = phase1_dir / "01_search_results.parquet"
        if search_path.exists():
            df = pd.read_parquet(search_path)
        else:
            csv_path = phase1_dir / "01_search_results.csv"
            df = pd.read_csv(csv_path)
        counts["records_identified"] = len(df)
    except Exception as e:
        logger.warning(f"Failed to compute search count: {e}")
    # Deduplication: compute duplicates removed
    if dedup_dir is not None:
        try:
            # Deduplicator outputs deduplicated parquet and duplicates map
            dedup_path = dedup_dir / "deduplicated_papers.parquet"
            dup_path = dedup_dir / "duplicate_map.csv"
            if dedup_path.exists():
                dedup_df = pd.read_parquet(dedup_path)
                counts["records_after_dedup"] = len(dedup_df)
            if dup_path.exists():
                dup_df = pd.read_csv(dup_path)
                counts["duplicates_removed"] = len(dup_df)
            else:
                # Fallback: difference between phase1 and deduplicated
                if "records_after_dedup" in counts:
                    counts["duplicates_removed"] = max(
                        0, counts["records_identified"] - counts["records_after_dedup"]
                    )
        except Exception as e:
            logger.warning(f"Failed to compute duplicates removed: {e}")
    # Screening counts
    if screening_dir is not None:
        try:
            screen_path = screening_dir / "screening_results.parquet"
            if screen_path.exists():
                scr_df = pd.read_parquet(screen_path)
            else:
                csv_path = screening_dir / "screening_results.csv"
                scr_df = pd.read_csv(csv_path)
            counts["records_screened"] = len(scr_df)
            # Decision column may be 'decision' or 'Decision'
            col_candidates = [c for c in scr_df.columns if c.lower() == "decision"]
            if col_candidates:
                decision_col = col_candidates[0]
                # Count excluded (exclude or maybe treated as excluded)
                excluded_mask = scr_df[decision_col].str.lower().isin([
                    "exclude",
                    "excluded",
                ])
                counts["records_excluded"] = int(excluded_mask.sum())
                # Included count
                included_mask = scr_df[decision_col].str.lower().isin(["include", "included"])
                counts["studies_included"] = int(included_mask.sum())
                # Reports assessed is the number screened (qualify for full text)
                counts["reports_assessed"] = counts["records_screened"] - counts["records_excluded"]
                # Reports excluded at full text stage can be derived if available
                counts["reports_excluded"] = counts["reports_assessed"] - counts["studies_included"]
            else:
                counts["records_screened"] = len(scr_df)
        except Exception as e:
            logger.warning(f"Failed to compute screening counts: {e}")
    return counts


def generate_prisma_diagram(counts: Dict[str, int], output_path: Path) -> None:
    """Generate a PRISMA flow diagram and save to file.

    Args:
        counts: Dictionary of counts as returned by ``compute_prisma_counts``.
        output_path: Path to save the diagram (PNG or SVG).

    The function draws simple rectangular boxes connected by arrows to
    illustrate the flow of records through the systematic review
    process.  The sizes of boxes are not scaled by counts.
    """
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axis("off")
    # Coordinates for boxes (x, y)
    positions = {
        "records_identified": (0.0, 0.8),
        "duplicates_removed": (0.0, 0.65),
        "records_screened": (0.0, 0.5),
        "records_excluded": (0.3, 0.35),
        "reports_assessed": (0.0, 0.35),
        "reports_excluded": (0.3, 0.2),
        "studies_included": (0.0, 0.2),
    }
    # Box size
    width, height = 0.25, 0.08
    def draw_box(label: str, text: str):
        x, y = positions[label]
        box = FancyBboxPatch(
            (x, y), width, height,
            boxstyle="round,pad=0.02", fc="white", ec="black"
        )
        ax.add_patch(box)
        ax.text(
            x + width / 2, y + height / 2, text,
            ha="center", va="center", fontsize=8, wrap=True
        )
    # Draw boxes with counts
    draw_box(
        "records_identified",
        f"Records identified\n(n = {counts.get('records_identified', 0)})",
    )
    draw_box(
        "duplicates_removed",
        f"Records after duplicates removed\n(n = {counts.get('records_identified', 0) - counts.get('duplicates_removed', 0)})",
    )
    draw_box(
        "records_screened",
        f"Records screened\n(n = {counts.get('records_screened', 0)})",
    )
    draw_box(
        "records_excluded",
        f"Records excluded\n(n = {counts.get('records_excluded', 0)})",
    )
    draw_box(
        "reports_assessed",
        f"Full‑text articles assessed for eligibility\n(n = {counts.get('reports_assessed', 0)})",
    )
    draw_box(
        "reports_excluded",
        f"Full‑text articles excluded\n(n = {counts.get('reports_excluded', 0)})",
    )
    draw_box(
        "studies_included",
        f"Studies included in review\n(n = {counts.get('studies_included', 0)})",
    )
    # Draw arrows
    def arrow(start: str, end: str):
        x1, y1 = positions[start]
        x2, y2 = positions[end]
        # Adjust start and end points to be at middle bottom/top of boxes
        start_xy = (x1 + width / 2, y1)
        end_xy = (x2 + width / 2, y2 + height)
        ax.annotate(
            "",
            xy=end_xy, xytext=start_xy,
            arrowprops=dict(arrowstyle="->", lw=1.0),
        )
    arrow("records_identified", "duplicates_removed")
    arrow("duplicates_removed", "records_screened")
    arrow("records_screened", "records_excluded")
    arrow("records_screened", "reports_assessed")
    arrow("reports_assessed", "reports_excluded")
    arrow("reports_assessed", "studies_included")
    # Save figure
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    logger.info(f"PRISMA diagram saved to {output_path}")