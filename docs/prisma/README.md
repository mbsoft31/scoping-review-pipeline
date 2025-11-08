# PRISMA Module

The **prisma** module produces PRISMA flow diagrams—standardised charts that map the flow of information through the systematic review process.  PRISMA diagrams show how many records were identified, screened, assessed for eligibility and included in the review【225382337630412†L102-L110】.

## Functions

Two utility functions are provided in [`diagram.py`](../../src/srp/prisma/diagram.py):

- `compute_prisma_counts(phase1_dir: Path, screening_dir: Optional[Path] = None, dedup_dir: Optional[Path] = None) -> Dict[str, int]`: Reads Phase 1 search results, screening results and (optionally) deduplication results to compute the numbers needed for a PRISMA diagram.  Keys in the returned dictionary include:
  - `records_identified`: Total number of papers retrieved from all databases during search.
  - `duplicates_removed`: Number of duplicate records removed.
  - `records_screened`: Number of records screened (after deduplication).
  - `records_excluded`: Number of records excluded during screening.
  - `reports_assessed`: Number of full‑text articles assessed for eligibility.
  - `reports_excluded`: Number of full‑text articles excluded.
  - `studies_included`: Number of studies included in the qualitative synthesis.

  If files are missing or counts cannot be computed, the function logs a warning and leaves the count at zero.

- `generate_prisma_diagram(counts: Dict[str, int], output_path: Path) -> None`: Draws a simple PRISMA flow chart using Matplotlib.  It places labelled boxes for each stage (records identified, after duplicates, screened, excluded, full‑text assessed, excluded, included) and connects them with arrows.  The diagram is saved to the specified file (PNG or SVG).  The counts dictionary should come from `compute_prisma_counts()`.

## CLI integration

The CLI offers a `prisma` command:

```bash
srp prisma --phase1-dir output/phase1_2025-11-08 --screening-dir output/phase1.5_2025-11-08 --dedup-dir output/phase2_2025-11-08 --output prisma.png
```

This command computes the counts based on the provided directories and writes a PRISMA flow diagram to `prisma.png`.  If deduplication or screening directories are omitted, corresponding counts default to zero.