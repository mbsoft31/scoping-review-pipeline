# CLI Module

The **cli** module exposes the pipeline’s functionality via a set of Typer commands.  Running `python -m srp.cli.main` or the installed `srp` entrypoint provides an intuitive command‑line interface for each phase of the workflow.

## Commands

Below is a summary of the key commands defined in [`main.py`](../../src/srp/cli/main.py).  Each command prints helpful messages and interacts with other modules to perform its task.

### `serve`

Starts the FastAPI web server.  Options:

- `--host`: Hostname (default `127.0.0.1`).
- `--port`: Port (default `8000`).
- `--reload/--no-reload`: Enable auto‑reload for development.

Example:

```bash
srp serve --host 0.0.0.0 --port 8000 --reload
```

### `phase1`

Performs Phase 1 search across selected databases.  Options:

- `--query` / `-q`: A single search query.
- `--query-file`: File with one query per line.
- `--domain`: Domain name to load predefined terms from `config/defaults.yaml`.
- `--start-date` / `--end-date`: Date range filters (YYYY‑MM‑DD).
- `--db`: Comma‑separated list of databases (openalex, semantic_scholar, crossref, arxiv).
- `--limit`: Maximum results per source.
- `--output` / `-o`: Output directory (defaults to a timestamped folder under `output/`).
- `--resume/--no-resume`: Resume from cached pages.

It calls the `SearchOrchestrator` and writes `01_search_results.parquet` and `.csv` files along with a `01_queries.md` listing all executed queries.

### `screen`

Runs Phase 1.5 screening on Phase 1 results.  Options:

- `phase1_dir`: Input directory containing `01_search_results.parquet`.
- `--criteria`: YAML file defining inclusion and exclusion criteria.
- `--vocabulary`: Optional YAML file defining domain vocabulary.
- `--mode`: Screening mode (`auto`, `semi_auto`, `hitl`, `manual`).
- `--auto-threshold`, `--maybe-threshold`: Thresholds for automatic decisions.
- `--model`: Name of the sentence transformer model.
- `--output` / `-o`: Directory to save screening results.

In `semi_auto` and `hitl` modes, it creates a human review queue via `HITLReviewer`.

### `review`

Launches an interactive CLI for human reviewers to confirm or override screening decisions.  Options:

- `screening_dir`: Directory containing `review/` subfolder and screening results.
- `--reviewer`: Name or ID of the reviewer.
- `--batch`: Number of papers to review in one batch.

The reviewer loops through uncertain papers, records decisions and notes, and prints summary statistics upon completion.

### `prisma`

Generates a PRISMA flow diagram.  Options:

- `--phase1-dir`: Phase 1 output directory.
- `--screening-dir`: Phase 1.5 output directory (optional).
- `--dedup-dir`: Phase 2 output directory (optional).
- `--output` / `-o`: Path to save the diagram (PNG/SVG).

This command calls `compute_prisma_counts()` and `generate_prisma_diagram()` in the `prisma` module.

### `meta`

Runs a simple meta‑analysis from a CSV file of effect sizes and generates a forest plot.  Options:

- `--effects-csv`: Path to a CSV file with columns for study ID, effect estimate and standard error.
- `--effect-col`, `--se-col`, `--study-col`: Column names in the CSV (defaults `effect`, `se`, `study_id`).
- `--method`: Pooling method (`fixed` or `random`).
- `--output` / `-o`: Path to save the forest plot.

It reads the CSV, creates `EffectSize` objects, computes the pooled effect via `MetaAnalyzer`, and invokes `create_forest_plot()`.

## Notes

Commands for data extraction, quality assessment and living reviews are planned but may be implemented in separate scripts.  All CLI commands display progress bars, colour‑coded messages and summarised results using the [`rich`](https://rich.readthedocs.io/) library.