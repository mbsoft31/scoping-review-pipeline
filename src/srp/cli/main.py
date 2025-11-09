"""CLI application using Typer for the systematic review pipeline."""

import asyncio
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from srp.core.models import Paper
from srp.io.validation import validate_phase_output
from ..config.settings import settings
from ..search.orchestrator import SearchOrchestrator
from ..search.query_builder import QueryBuilder, load_domain_terms
from ..io.paths import create_output_dir
from ..utils.logging import get_logger
# Import PRISMA and meta‑analysis helpers.  These imports are light
# and only bring in small wrappers around matplotlib.  Heavy modules
# (like transformers for screening) remain lazily loaded.
from ..prisma.diagram import generate_prisma_diagram, compute_prisma_counts  # noqa: E402
from ..meta.analyzer import MetaAnalyzer, EffectSize  # noqa: E402
from ..meta.forest_plot import create_forest_plot  # noqa: E402

# Screening components are imported lazily inside the screening
# commands to avoid importing heavy dependencies (such as
# sentence‑transformers) during normal operation.  See the
# ``screen`` and ``review`` functions for details.
from srp.web.app import start_server as _start_web_server

app = typer.Typer(
    name="srp",
    help="Systematic Review Pipeline - Modular literature review tool",
    add_completion=False,
)

console = Console()
logger = get_logger(__name__)


@app.command()
def serve(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Hostname to bind the web server to.",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        help="Port for the web server.",
    ),
    reload: bool = typer.Option(
        False,
        "--reload/--no-reload",
        help="Enable auto-reload (development only).",
    ),
) -> None:
    """Start the interactive web dashboard.

    Launches a FastAPI server exposing the SRP web interface. Use
    ``--reload`` in development to auto-restart on code changes.
    """
    console.print(f"[bold blue]Starting web server[/bold blue] at http://{host}:{port}")
    try:
        _start_web_server(host=host, port=port, reload=reload)
    except Exception as exc:
        logger.error(f"Failed to start web server: {exc}")


@app.command()
def phase1(
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Single search query"),
    query_file: Optional[Path] = typer.Option(None, "--query-file", help="File with queries (one per line)"),
    domain: Optional[str] = typer.Option(None, "--domain", help="Predefined domain (ai_bias, climate_adaptation)"),
    start_date: str = typer.Option(settings.default_start_date, "--start-date", help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(settings.default_end_date, "--end-date", help="End date (YYYY-MM-DD)"),
    databases: str = typer.Option("openalex", "--db", help="Comma-separated databases (openalex,semantic_scholar)"),
    limit_per_source: Optional[int] = typer.Option(None, "--limit", "-n", help="Maximum papers per source"),
    s2_page_size: int = typer.Option(20, "--s2-page-size", help="S2 page size (max 100)"),
    s2_per_page_delay: float = typer.Option(1.3, "--s2-per-page-delay", help="S2 delay between pages (seconds)"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory (default: timestamped)"),
    resume: bool = typer.Option(True, "--resume/--no-resume", help="Resume from cache"),
):
    """Phase 1: Search and collect papers from academic databases."""
    console.print(f"[bold blue]Starting Phase 1: Search[/bold blue]")
    # Determine queries
    queries: List[str] = []
    if query:
        queries = [query]
    elif query_file and query_file.exists():
        queries = [line.strip() for line in query_file.read_text().splitlines() if line.strip()]
    elif domain:
        console.print(f"[cyan]Generating queries for domain: {domain}[/cyan]")
        terms = load_domain_terms(domain)
        builder = QueryBuilder()
        queries = builder.generate_systematic_queries(
            core_terms=terms["core"],
            method_terms=terms["method"],
            context_terms=terms["context"],
        )
        console.print(f"[green]Generated {len(queries)} queries[/green]")
    else:
        console.print("[red]Error: Must provide --query, --query-file, or --domain[/red]")
        raise typer.Exit(1)
    # Parse dates
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    # Create output directory
    if output_dir is None:
        output_dir = create_output_dir("phase1")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"Date range: {start} to {end}")
    console.print(f"Databases: {databases}")
    console.print(f"Queries: {len(queries)}")
    console.print(f"Output: {output_dir}")
    db_list = [db.strip() for db in databases.split(",")]
    configs = {
        "semantic_scholar": {
            "page_size": s2_page_size,
            "per_page_delay": s2_per_page_delay,
        }
    }
    asyncio.run(
        _run_phase1(
            queries=queries,
            start_date=start,
            end_date=end,
            databases=db_list,
            limit_per_source=limit_per_source,
            output_dir=output_dir,
            configs=configs,
            resume=resume,
        )
    )
    console.print(f"\n[bold green]✓ Phase 1 complete![/bold green]")
    console.print(f"Results saved to: {output_dir}")


async def _run_phase1(
    queries: List[str],
    start_date: date,
    end_date: date,
    databases: List[str],
    limit_per_source: Optional[int],
    output_dir: Path,
    configs: dict,
    resume: bool,
) -> None:
    import pandas as pd
    orchestrator = SearchOrchestrator()
    all_papers: List[Paper] = []
    # Save query list
    query_path = output_dir / "01_queries.md"
    with open(query_path, "w") as f:
        f.write("# Search Queries\n\n")
        for i, q in enumerate(queries, 1):
            f.write(f"{i}. `{q}`\n")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Searching {len(databases)} databases...", total=len(queries) * len(databases))
        for query_idx, query in enumerate(queries, 1):
            console.print(f"\n[cyan]Query {query_idx}/{len(queries)}: {query}[/cyan]")
            for db in databases:
                progress.update(task, description=f"[{db}] {query[:50]}...")
                try:
                    papers = await orchestrator.search_source(
                        source=db,
                        query=query,
                        start_date=start_date,
                        end_date=end_date,
                        limit=limit_per_source,
                        config=configs.get(db),
                        resume=resume,
                    )
                    all_papers.extend(papers)
                    console.print(f"  [{db}] Found {len(papers)} papers")
                except Exception as e:
                    console.print(f"  [[red]{db}] Error: {e}[/red]")
                progress.advance(task)
    orchestrator.close()
    # Display summary
    summary_table = Table(title="Search Summary")
    summary_table.add_column("Database", style="cyan")
    summary_table.add_column("Papers", style="green", justify="right")
    for db in databases:
        db_count = sum(1 for p in all_papers if p.source.database == db)
        summary_table.add_row(db, str(db_count))
    summary_table.add_row("[bold]Total[/bold]", f"[bold]{len(all_papers)}[/bold]")
    console.print(summary_table)
    # Save results
    if all_papers:
        df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in all_papers])
        parquet_path = output_dir / "01_search_results.parquet"
        df.to_parquet(parquet_path, index=False)
        console.print(f"Saved: {parquet_path}")
        csv_path = output_dir / "01_search_results.csv"
        df.to_csv(csv_path, index=False)
        console.print(f"Saved: {csv_path}")
        import json
        stats = {
            "queries": queries,
            "num_queries": len(queries),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "databases": databases,
            "total_papers": len(all_papers),
            "papers_by_source": {db: sum(1 for p in all_papers if p.source.database == db) for db in databases},
            "timestamp": datetime.utcnow().isoformat(),
        }
        stats_path = output_dir / "01_stats.json"
        stats_path.write_text(json.dumps(stats, indent=2))
        console.print(f"Saved: {stats_path}")
    else:
        console.print("[yellow]No papers found[/yellow]")


@app.command()
def phase2(
    phase1_dir: Path = typer.Argument(..., help="Phase 1 output directory", exists=True),
    citation_max_papers: int = typer.Option(200, "--citation-max-papers", help="Max papers for citation enrichment"),
    refs_per_paper: int = typer.Option(100, "--refs-per-paper", help="Max references per paper"),
    citation_sources: str = typer.Option("semantic_scholar", "--citation-sources", help="Comma-separated sources for citations"),
    fuzzy_threshold: float = typer.Option(0.85, "--fuzzy-threshold", help="Fuzzy title match threshold (0-1)"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory (default: timestamped)"),
):
    """Phase 2: Deduplicate, enrich with citations, and compute influence scores."""
    console.print(f"[bold blue]Starting Phase 2: Analysis[/bold blue]")
    console.print(f"Input: {phase1_dir}")
    if output_dir is None:
        output_dir = create_output_dir("phase2")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"Output: {output_dir}")
    # Load phase1 results
    parquet_path = phase1_dir / "01_search_results.parquet"
    if not parquet_path.exists():
        console.print(f"[red]Error: {parquet_path} not found[/red]")
        raise typer.Exit(1)
    console.print(f"[cyan]Loading papers from {parquet_path}...[/cyan]")
    import pandas as pd
    from ..core.models import Source
    df = pd.read_parquet(parquet_path)
    papers: List[Paper] = []
    for _, row in df.iterrows():
        try:
            source_data = row.get("source")
            if isinstance(source_data, dict):
                source = Source(**source_data)
            else:
                source = Source(database="unknown", query="", timestamp="")
            paper = Paper(
                paper_id=row["paper_id"],
                doi=row.get("doi"),
                arxiv_id=row.get("arxiv_id"),
                title=row["title"],
                abstract=row.get("abstract"),
                authors=row.get("authors", []),
                year=row.get("year"),
                venue=row.get("venue"),
                fields_of_study=row.get("fields_of_study", []),
                citation_count=row.get("citation_count", 0),
                influential_citation_count=row.get("influential_citation_count", 0),
                is_open_access=row.get("is_open_access", False),
                open_access_pdf=row.get("open_access_pdf"),
                external_ids=row.get("external_ids", {}),
                source=source,
            )
            papers.append(paper)
        except Exception as e:
            logger.warning(f"Failed to parse paper: {e}")
            continue
    console.print(f"[green]Loaded {len(papers)} papers[/green]")
    asyncio.run(
        _run_phase2(
            papers=papers,
            output_dir=output_dir,
            citation_max_papers=citation_max_papers,
            refs_per_paper=refs_per_paper,
            citation_sources=[s.strip() for s in citation_sources.split(",")],
            fuzzy_threshold=fuzzy_threshold,
        )
    )
    console.print(f"\n[bold green]✓ Phase 2 complete![/bold green]")
    console.print(f"Results saved to: {output_dir}")


async def _run_phase2(
    papers: List[Paper],
    output_dir: Path,
    citation_max_papers: int,
    refs_per_paper: int,
    citation_sources: List[str],
    fuzzy_threshold: float,
) -> None:
    import json
    import pandas as pd
    from ..dedup.deduplicator import Deduplicator
    from ..enrich.citations import CitationEnricher
    from ..enrich.influence import InfluenceScorer
    from ..core.models import Paper
    # Step 1: Deduplication
    console.print("\n[cyan]Step 1: Deduplicating papers...[/cyan]")
    deduplicator = Deduplicator(fuzzy_threshold=fuzzy_threshold)
    deduped_papers, clusters = deduplicator.deduplicate(papers)
    console.print(f"[green]✓ Deduplicated: {len(papers)} -> {len(deduped_papers)} papers[/green]")
    console.print(f"  Removed {len(papers) - len(deduped_papers)} duplicates in {len(clusters)} clusters")
    deduped_df = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in deduped_papers])
    deduped_parquet = output_dir / "02_deduped_papers.parquet"
    deduped_df.to_parquet(deduped_parquet, index=False)
    console.print(f"Saved: {deduped_parquet}")
    deduped_csv = output_dir / "02_deduped_papers.csv"
    deduped_df.to_csv(deduped_csv, index=False)
    console.print(f"Saved: {deduped_csv}")
    # Step 2: Citation enrichment
    console.print("\n[cyan]Step 2: Fetching citations...[/cyan]")
    enricher = CitationEnricher(max_papers=citation_max_papers, refs_per_paper=refs_per_paper)
    references = await enricher.fetch_references(papers=deduped_papers, sources=citation_sources)
    console.print(f"[green]✓ Fetched {len(references)} references[/green]")
    # Step 3: Resolve citations
    console.print("\n[cyan]Step 3: Resolving citations...[/cyan]")
    resolved_refs, citation_stats = enricher.resolve_citations(references=references, papers=deduped_papers)
    console.print(f"[green]✓ Resolved citations[/green]")
    console.print(f"  In-corpus: {citation_stats['in_corpus_citations']}")
    console.print(f"  External: {citation_stats['external_citations']}")
    refs_df = pd.DataFrame([r.model_dump() for r in resolved_refs])
    refs_parquet = output_dir / "02_citation_edges.parquet"
    refs_df.to_parquet(refs_parquet, index=False)
    console.print(f"Saved: {refs_parquet}")
    # Step 4: Influence scoring
    console.print("\n[cyan]Step 4: Computing influence scores...[/cyan]")
    scorer = InfluenceScorer()
    influence_df = scorer.compute_influence_scores(papers=deduped_papers, references=resolved_refs)
    console.print(f"[green]✓ Computed influence scores[/green]")
    seminal_path = output_dir / "02_seminal_papers.csv"
    influence_df.to_csv(seminal_path, index=False)
    console.print(f"Saved: {seminal_path}")
    # Display top 10
    console.print("\n[bold]Top 10 Most Influential Papers:[/bold]")
    table = Table(title="Seminal Papers")
    table.add_column("Rank", style="cyan", width=4)
    table.add_column("Title", style="white", width=50)
    table.add_column("Year", style="green", width=4)
    table.add_column("Citations", style="yellow", justify="right", width=8)
    table.add_column("Influence", style="magenta", justify="right", width=10)
    for _, row in influence_df.head(10).iterrows():
        table.add_row(
            str(row["rank"]),
            row["title"][:47] + "..." if len(row["title"]) > 50 else row["title"],
            str(row["year"]) if pd.notna(row["year"]) else "N/A",
            str(row["total_citations"]),
            f"{row['influence_score']:.3f}",
        )
    console.print(table)
    # Save graph stats
    G = scorer.build_citation_graph(deduped_papers, resolved_refs)
    graph_stats = scorer.get_graph_statistics(G)
    stats = {
        "deduplication": {
            "original_papers": len(papers),
            "deduplicated_papers": len(deduped_papers),
            "duplicates_removed": len(papers) - len(deduped_papers),
            "clusters": len(clusters),
        },
        "citations": citation_stats,
        "graph": graph_stats,
        "timestamp": datetime.utcnow().isoformat(),
    }
    stats_path = output_dir / "02_graph_stats.json"
    stats_path.write_text(json.dumps(stats, indent=2))
    console.print(f"\nSaved: {stats_path}")


@app.command()
def version() -> None:
    """Show version information."""
    from .. import __version__
    console.print(f"Systematic Review Pipeline v{__version__}")


# -----------------------------------------------------------------------------
# Validation and Export Commands
# -----------------------------------------------------------------------------

@app.command()
def validate(
    phase_dir: Path = typer.Argument(..., help="Phase output directory", exists=True),
    check_schema: bool = typer.Option(True, "--check-schema/--no-check-schema"),
    check_duplicates: bool = typer.Option(True, "--check-duplicates/--no-check-duplicates"),
    check_citations: bool = typer.Option(True, "--check-citations/--no-check-citations"),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as errors"),
) -> None:
    """
    Validate data quality and integrity for a phase directory.

    Examples:
        srp validate output/phase1_20241107_173045/
        srp validate output/phase2_20241107_180030/ --strict
    """
    passed = validate_phase_output(
        phase_dir=phase_dir,
        check_schema=check_schema,
        check_duplicates=check_duplicates,
        check_citations=check_citations,
        strict=strict,
    )
    if passed:
        console.print("\n[bold green]✓ Validation passed![/bold green]")
        raise typer.Exit(0)
    else:
        console.print("\n[bold red]✗ Validation failed![/bold red]")
        raise typer.Exit(1)


@app.command()
def export(
    phase_dir: Path = typer.Argument(..., help="Phase output directory", exists=True),
    format: str = typer.Option(
        "bibtex,csv", "--format", help="Export formats (comma-separated): bibtex,csv,json"
    ),
    top_papers: Optional[int] = typer.Option(
        None, "--top-papers", "-n", help="Export only top N papers"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory (default: same as input)"
    ),
) -> None:
    """
    Export data from a phase directory in various formats.

    Examples:
        srp export output/phase2_20241107_173500/ --format bibtex,csv,json --top-papers 100
    """
    import json as _json
    console.print(f"[bold blue]Exporting data from {phase_dir}[/bold blue]")
    # Load papers
    parquet_files = list(phase_dir.glob("*papers.parquet"))
    if not parquet_files:
        console.print("[red]Error: No parquet files found[/red]")
        raise typer.Exit(1)
    console.print(f"Loading papers from {parquet_files[0]}...")
    df = __import__("pandas").read_parquet(parquet_files[0])  # lazy import to avoid overhead
    papers: List[Paper] = []
    from ..core.models import Paper, Source
    for _, row in df.iterrows():
        try:
            source_data = row.get("source", {})
            if isinstance(source_data, dict):
                source = Source(**source_data)
            else:
                source = Source(database="unknown", query="", timestamp="")
            paper = Paper(
                paper_id=row["paper_id"],
                doi=row.get("doi"),
                arxiv_id=row.get("arxiv_id"),
                title=row.get("title", "Untitled"),
                abstract=row.get("abstract"),
                authors=row.get("authors", []),
                year=row.get("year"),
                venue=row.get("venue"),
                citation_count=row.get("citation_count", 0),
                external_ids=row.get("external_ids", {}),
                source=source,
            )
            papers.append(paper)
        except Exception:
            continue
    console.print(f"[green]Loaded {len(papers)} papers[/green]")
    # Filter top papers by influence score if requested
    seminal_file = phase_dir / "02_seminal_papers.csv"
    if seminal_file.exists() and top_papers:
        console.print("Sorting by influence score...")
        influence_df = __import__("pandas").read_csv(seminal_file)
        top_ids = influence_df.head(top_papers)["paper_id"].tolist()
        papers = [p for p in papers if p.paper_id in top_ids]
    elif top_papers:
        papers = papers[:top_papers]
    # Determine output directory
    out_dir = output_dir or phase_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # Handle export formats
    formats = [f.strip().lower() for f in format.split(",")]
    for fmt in formats:
        if fmt == "bibtex":
            console.print(f"\n[cyan]Exporting BibTeX...[/cyan]")
            exporter = BibTeXExporter()
            bib_path = out_dir / "references.bib"
            exporter.export(papers, bib_path, top_n=None)
            console.print(f"[green]✓ Saved: {bib_path}[/green]")
        elif fmt == "csv":
            console.print(f"\n[cyan]Exporting CSV...[/cyan]")
            csv_path = out_dir / "papers_export.csv"
            export_df = __import__("pandas").DataFrame([
                p.model_dump(mode="json", exclude={"raw_data"}) for p in papers
            ])
            export_df.to_csv(csv_path, index=False)
            console.print(f"[green]✓ Saved: {csv_path}[/green]")
        elif fmt == "json":
            console.print(f"\n[cyan]Exporting JSON...[/cyan]")
            json_path = out_dir / "papers_export.json"
            json_data = [p.model_dump(mode="json", exclude={"raw_data"}) for p in papers]
            json_path.write_text(_json.dumps(json_data, indent=2), encoding="utf-8")
            console.print(f"[green]✓ Saved: {json_path}[/green]")
        else:
            console.print(f"[yellow]⚠ Unknown format: {fmt}[/yellow]")
    console.print("\n[bold green]✓ Export complete![/bold green]")


# -----------------------------------------------------------------------------
# Screening Commands (Phase 1.5)
# -----------------------------------------------------------------------------

@app.command()
def screen(
    phase1_dir: Path = typer.Argument(..., help="Phase 1 output directory", exists=True),
    criteria_file: Path = typer.Option(..., "--criteria", help="YAML file defining inclusion and exclusion criteria", exists=True),
    vocabulary_file: Optional[Path] = typer.Option(None, "--vocabulary", help="YAML file defining domain vocabulary"),
    mode: str = typer.Option("auto", "--mode", help="Screening mode: auto, semi_auto, hitl or manual"),
    auto_threshold: float = typer.Option(0.75, "--auto-threshold", help="Auto decision confidence threshold"),
    maybe_threshold: float = typer.Option(0.5, "--maybe-threshold", help="Maybe category threshold"),
    model: str = typer.Option("all-MiniLM-L6-v2", "--model", help="Sentence transformer model"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory for screening results"),
) -> None:
    """
    Phase 1.5: Screen papers with semantic matching and (optionally) a
    human‑in‑the‑loop workflow.

    The criteria YAML file should have ``inclusion`` and ``exclusion``
    sections defining lists of criteria.  The optional vocabulary YAML
    file can specify a ``domain`` and ``concepts`` for domain‑specific
    matching.
    """
    import yaml
    import pandas as pd
    from ..core.models import Paper, Source
    # Import screening classes lazily.  These imports may raise
    # exceptions if optional dependencies (sentence‑transformers, torch)
    # are missing, in which case we surface a helpful error message.
    try:
        from ..screening.models import ScreeningCriterion, ScreeningMode, DomainVocabulary
        from ..screening.screener import AutoScreener
        from ..screening.semantic_matcher import SemanticMatcher
        from ..screening.hitl import HITLReviewer
        from ..screening.models import ScreeningDecision  # noqa: F401
    except Exception as exc:
        console.print("[red]The screening module is not available. Please install optional dependencies (sentence-transformers, torch).[/red]")
        raise typer.Exit(1)
    # Determine output directory
    if output_dir is None:
        out_dir = create_output_dir("phase1.5")
    else:
        out_dir = output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[bold blue]Starting Screening (Phase 1.5)[/bold blue]")
    console.print(f"Input: {phase1_dir}")
    console.print(f"Mode: {mode}")
    # Load papers from phase1 parquet
    parquet_path = phase1_dir / "01_search_results.parquet"
    if not parquet_path.exists():
        console.print(f"[red]Error: {parquet_path} not found[/red]")
        raise typer.Exit(1)
    df = pd.read_parquet(parquet_path)
    papers: List[Paper] = []
    for _, row in df.iterrows():
        src_data = row.get("source")
        if isinstance(src_data, dict):
            src = Source(**src_data)
        else:
            src = Source(database="unknown", query="", timestamp="")
        papers.append(
            Paper(
                paper_id=row["paper_id"],
                doi=row.get("doi"),
                arxiv_id=row.get("arxiv_id"),
                title=row["title"],
                abstract=row.get("abstract"),
                authors=row.get("authors", []),
                year=row.get("year"),
                venue=row.get("venue"),
                fields_of_study=row.get("fields_of_study", []),
                citation_count=row.get("citation_count", 0),
                influential_citation_count=row.get("influential_citation_count", 0),
                is_open_access=row.get("is_open_access", False),
                open_access_pdf=row.get("open_access_pdf"),
                external_ids=row.get("external_ids", {}),
                source=src,
            )
        )
    console.print(f"[green]Loaded {len(papers)} papers[/green]")
    # Load criteria from YAML
    with open(criteria_file, "r", encoding="utf-8") as f:
        criteria_data = yaml.safe_load(f) or {}
    inclusion_criteria = [ScreeningCriterion(**c) for c in criteria_data.get("inclusion", [])]
    exclusion_criteria = [ScreeningCriterion(**c) for c in criteria_data.get("exclusion", [])]
    console.print(f"Inclusion criteria: {len(inclusion_criteria)} | Exclusion criteria: {len(exclusion_criteria)}")
    # Load vocabulary if provided
    vocab = None
    if vocabulary_file:
        with open(vocabulary_file, "r", encoding="utf-8") as f:
            vocab_data = yaml.safe_load(f) or {}
        vocab = DomainVocabulary(**vocab_data)
        console.print(f"Loaded vocabulary: {vocab.domain} with {len(vocab.concepts)} concepts")
    # Initialise semantic matcher and screener
    console.print(f"Initialising semantic matcher with model [italic]{model}[/italic]...")
    matcher = SemanticMatcher(model_name=model)
    screener = AutoScreener(matcher=matcher, auto_threshold=auto_threshold, maybe_threshold=maybe_threshold)
    screening_mode = ScreeningMode(mode)
    # Screen papers
    console.print("[cyan]Screening papers...[/cyan]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task("Screening", total=len(papers))
        results: List[ScreeningResult] = []
        for paper in papers:
            result = screener.screen_paper(
                paper,
                inclusion_criteria,
                exclusion_criteria,
                vocabulary=vocab,
                mode=screening_mode,
            )
            results.append(result)
            progress.advance(task)
    # Summarise
    included = sum(1 for r in results if r.decision == ScreeningDecision.INCLUDE)
    excluded = sum(1 for r in results if r.decision == ScreeningDecision.EXCLUDE)
    maybe_cnt = sum(1 for r in results if r.decision == ScreeningDecision.MAYBE)
    table = Table(title="Screening Results")
    table.add_column("Decision", style="cyan")
    table.add_column("Count", style="yellow", justify="right")
    table.add_column("Percentage", style="magenta", justify="right")
    total = len(results)
    table.add_row("Include", str(included), f"{included/total*100:.1f}%")
    table.add_row("Exclude", str(excluded), f"{excluded/total*100:.1f}%")
    table.add_row("Maybe", str(maybe_cnt), f"{maybe_cnt/total*100:.1f}%")
    console.print(table)
    # Save screening results
    import json as _json
    import pandas as pd  # noqa: F401
    results_df = pd.DataFrame([r.model_dump() for r in results])
    results_df.to_parquet(out_dir / "screening_results.parquet", index=False)
    results_df.to_csv(out_dir / "screening_results.csv", index=False)
    console.print(f"[green]Saved: {out_dir / 'screening_results.parquet'}[/green]")
    # Semi-auto and HITL create review queue
    if mode in ["semi_auto", "hitl"]:
        console.print("\n[cyan]Creating review queue for uncertain papers...[/cyan]")
        reviewer = HITLReviewer(out_dir / "review")
        priority_ids = screener.active_learning_candidates(results, top_k=50)
        reviewer.create_review_queue(papers=papers, auto_results=results, priority_paper_ids=priority_ids)
        stats = reviewer.get_statistics()
        console.print(f"[green]Review queue created: {stats.get('remaining', 0)} papers to review[/green]")
        console.print(f"[dim]Use 'srp review' to start reviewing[/dim]")
    console.print(f"\n[bold green]✓ Screening complete![/bold green]")
    console.print(f"Output: {out_dir}")


@app.command()
def review(
    screening_dir: Path = typer.Argument(..., help="Screening output directory", exists=True),
    reviewer_name: str = typer.Option(..., "--reviewer", help="Name or ID of the reviewer"),
    batch_size: int = typer.Option(10, "--batch", help="Number of papers per review batch"),
) -> None:
    """
    Interactively review screening results in a human‑in‑the‑loop workflow.

    This command loads the review queue created by the ``screen``
    command and allows the user to confirm or override the automatic
    decisions.  A summary of the session is printed at the end.
    """
    from rich.prompt import Prompt, Confirm
    from rich.panel import Panel
    # Import review classes lazily
    try:
        from ..screening.models import ScreeningDecision  # type: ignore
        from ..screening.hitl import HITLReviewer  # type: ignore
    except Exception:
        console.print("[red]The screening module is not available. Please install optional dependencies.[/red]")
        raise typer.Exit(1)
    # Instantiate reviewer
    reviewer = HITLReviewer(screening_dir / "review")
    stats = reviewer.get_statistics()
    if not stats:
        console.print("[red]No review queue found in the specified directory.[/red]")
        raise typer.Exit(1)
    console.print(
        Panel(
            f"Human‑in‑the‑Loop Review\nReviewer: {reviewer_name}",
            title="📋 Paper Review",
            border_style="cyan",
        )
    )
    console.print(f"\nQueue Status: {stats['reviewed']}/{stats['total']} reviewed ({stats['remaining']} remaining)\n")
    # Review loop
    while True:
        next_papers = reviewer.get_next_for_review(batch_size)
        if not next_papers:
            console.print("[green]✓ All papers reviewed![/green]")
            break
        console.print(f"[cyan]Reviewing next {len(next_papers)} papers...[/cyan]\n")
        for i, info in enumerate(next_papers, 1):
            console.print(f"[bold]Paper {i}/{len(next_papers)}[/bold]")
            console.print(f"Title: {info['title']}")
            console.print(f"Authors: {info['authors']}")
            console.print(f"Year: {info['year']}")
            console.print(f"\nAuto Decision: [{info['auto_decision']}] (confidence: {info['auto_confidence']:.2f})")
            if info['exclusion_reasons']:
                console.print(f"Exclusion Reasons: {info['exclusion_reasons']}")
            if info['inclusion_tags']:
                console.print(f"Inclusion Tags: {info['inclusion_tags']}")
            # Ask for decision
            decision_str = Prompt.ask(
                "\nYour decision",
                choices=["include", "exclude", "maybe", "skip"],
                default="skip",
            )
            if decision_str == "skip":
                continue
            notes = Prompt.ask("Notes (optional)", default="")
            decision = ScreeningDecision(decision_str)
            reviewer.submit_review(
                paper_id=info["paper_id"],
                decision=decision,
                reviewer=reviewer_name,
                notes=notes,
            )
            console.print(f"[green]✓ Review submitted[/green]\n")
        if not Confirm.ask("\nReview next batch?"):
            break
    # Final summary
    stats = reviewer.get_statistics()
    console.print("\n[bold]Review Session Complete[/bold]")
    console.print(f"Papers reviewed: {stats['reviewed']}/{stats['total']}")
    console.print(f"Remaining: {stats['remaining']}")
    if stats.get("auto_agreement_rate"):
        console.print(f"Agreement with auto‑screening: {stats['auto_agreement_rate']*100:.1f}%")


# -----------------------------------------------------------------------------
# PRISMA diagram command
# -----------------------------------------------------------------------------

@app.command()
def prisma(
    phase1_dir: Path = typer.Option(..., help="Phase 1 output directory", exists=True),
    screening_dir: Optional[Path] = typer.Option(None, help="Screening results directory (phase1.5)"),
    dedup_dir: Optional[Path] = typer.Option(None, help="Deduplication results directory (phase2)"),
    output: Path = typer.Option(Path("prisma_diagram.png"), "--output", "-o", help="Output image file (PNG/SVG)"),
) -> None:
    """
    Generate a PRISMA flow diagram from pipeline outputs.

    This command computes record counts from the specified directories
    and renders a PRISMA flow chart saved to the given output file.
    """
    console.print("[bold blue]Generating PRISMA flow diagram[/bold blue]")
    counts = compute_prisma_counts(phase1_dir=phase1_dir, screening_dir=screening_dir, dedup_dir=dedup_dir)
    console.print(f"Counts: {counts}")
    generate_prisma_diagram(counts, output)
    console.print(f"[green]✓ PRISMA diagram saved to {output}[/green]")


# -----------------------------------------------------------------------------
# Meta‑analysis and forest plot command
# -----------------------------------------------------------------------------

@app.command()
def meta(
    effects_csv: Path = typer.Option(..., help="CSV file with effect sizes for meta‑analysis", exists=True),
    effect_col: str = typer.Option("effect", help="Column name for effect estimates"),
    se_col: str = typer.Option("se", help="Column name for standard errors"),
    study_col: str = typer.Option("study_id", help="Column name for study identifiers"),
    method: str = typer.Option("random", help="Pooling method: 'fixed' or 'random'"),
    out: Path = typer.Option(Path("forest_plot.png"), "--output", "-o", help="Output image file for forest plot"),
) -> None:
    """
    Perform a simple meta‑analysis and generate a forest plot.

    The input CSV must contain columns for study identifiers, effect
    estimates and standard errors.  The pooled effect is computed
    using a fixed or random effects model.  A forest plot is
    generated and saved to the specified output file.
    """
    console.print("[bold blue]Running meta‑analysis[/bold blue]")
    import pandas as pd  # local import to avoid global dependency
    # Load effect size data
    df = pd.read_csv(effects_csv)
    if not {study_col, effect_col, se_col}.issubset(df.columns):
        console.print("[red]Error: specified columns not found in CSV file[/red]")
        raise typer.Exit(1)
    # Build effect size objects
    effect_sizes = []
    for _, row in df.iterrows():
        try:
            effect = float(row[effect_col])
            se = float(row[se_col])
        except Exception:
            continue
        # Approximate CI from standard error
        ci_lower = effect - 1.96 * se
        ci_upper = effect + 1.96 * se
        weight = 1 / (se ** 2) if se > 0 else 0.0
        effect_sizes.append(
            EffectSize(
                study_id=str(row[study_col]),
                effect=effect,
                se=se,
                ci_lower=ci_lower,
                ci_upper=ci_upper,
                weight=weight,
            )
        )
    if not effect_sizes:
        console.print("[red]No valid effect sizes found in CSV[/red]")
        raise typer.Exit(1)
    analyzer = MetaAnalyzer()
    pooled = analyzer.compute_pooled_effect(effect_sizes, method=method)
    console.print(f"Pooled effect: {pooled['pooled_effect']:.4f} ± {pooled['standard_error']:.4f}")
    # Generate forest plot
    df_plot = analyzer.generate_forest_plot_data(effect_sizes, pooled)
    create_forest_plot(df_plot, out)
    console.print(f"[green]✓ Forest plot saved to {out}[/green]")


# -----------------------------------------------------------------------------
# LLM fine‑tuning, extraction and cost reporting commands
# -----------------------------------------------------------------------------

@app.command()
def train(
    screening_dir: Path = typer.Argument(..., exists=True, help="Directory containing human screening results"),
    phase1_dir: Path = typer.Argument(..., exists=True, help="Directory containing phase 1 search results"),
    model: str = typer.Option("allenai/scibert_scivocab_uncased", "--model", help="Base model to fine‑tune"),
    epochs: int = typer.Option(1, "--epochs", help="Number of epochs (stub)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Directory to save fine‑tuned model"),
) -> None:
    """Fine‑tune a classifier on human screening decisions (stub).

    This command prepares training data from human‑reviewed screening
    results and invokes the fine‑tuning pipeline.  In this stub
    implementation no actual training is performed; metadata is
    recorded and the resulting model directory is returned.
    """
    console.print("[bold cyan]Fine‑tuning classifier (stub)[/bold cyan]")
    # Import lazily to avoid heavy dependencies on startup
    from ..llm.fine_tuning import FineTuningPipeline
    from ..screening.hitl import HITLReviewer
    from ..core.models import Paper, Source
    from ..screening.models import ScreeningResult, ScreeningDecision, ScreeningMode
    import pandas as pd
    # Load human decisions
    reviewer = HITLReviewer(screening_dir / "review")
    decisions_df = reviewer.export_final_decisions(screening_dir / "final_decisions.csv")
    # Load phase 1 papers
    search_file = phase1_dir / "01_search_results.parquet"
    if not search_file.exists():
        console.print(f"[red]Search results file not found: {search_file}[/red]")
        raise typer.Exit(1)
    papers_df = pd.read_parquet(search_file)
    # Map papers
    papers_map: Dict[str, Paper] = {}
    for _, row in papers_df.iterrows():
        src = row.get("source", {})
        if isinstance(src, dict):
            source = Source(**src)
        else:
            source = Source(database="unknown", query="", timestamp="")
        paper = Paper(
            paper_id=row["paper_id"],
            title=row["title"],
            abstract=row.get("abstract"),
            year=row.get("year"),
            citation_count=row.get("citation_count", 0),
            external_ids=row.get("external_ids", {}),
            source=source,
        )
        papers_map[paper.paper_id] = paper
    # Build screening results
    screening_results: List[ScreeningResult] = []
    for _, row in decisions_df.iterrows():
        decision_str = row.get("final_decision")
        if decision_str not in {"include", "exclude"}:
            continue
        decision = ScreeningDecision(decision_str)
        screening_results.append(
            ScreeningResult(
                paper_id=row["paper_id"],
                decision=decision,
                confidence=1.0,
                mode=ScreeningMode.MANUAL,
            )
        )
    papers_for_training = [papers_map[p.paper_id] for p in screening_results if p.paper_id in papers_map]
    if not papers_for_training:
        console.print("[red]No labeled papers available for training[/red]")
        raise typer.Exit(1)
    pipeline = FineTuningPipeline(base_model=model, output_dir=output)
    # Prepare training data and fine tune (stub)
    _train_papers, _train_labels = pipeline.prepare_training_data(screening_results, papers_for_training)
    model_path = pipeline.fine_tune_with_lora(train_papers=_train_papers, train_labels=_train_labels)
    console.print(f"[green]Model saved to {model_path} (stub)[/green]")
    inference_path = pipeline.export_for_inference(model_path)
    console.print(f"[green]Inference model ready at {inference_path}[/green]")


@app.command()
def extract(
    phase_dir: Path = typer.Argument(..., exists=True, help="Directory containing phase 1 or screening results"),
    use_llm: bool = typer.Option(False, "--use-llm", help="Allow LLM fallback when regex extraction is incomplete"),
    min_citations: int = typer.Option(50, "--min-citations", help="Minimum citation count to trigger LLM extraction"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Directory to write extracted data"),
) -> None:
    """Extract structured data from papers using a hybrid extractor.

    Papers are loaded from the specified phase directory.  A hybrid
    extractor attempts regex‑based extraction first and falls back to
    the LLM router if enabled and the paper has sufficient citation
    count.  Results are saved in both Parquet and CSV formats.
    """
    console.print("[bold purple]Data extraction (hybrid)[/bold purple]")
    import pandas as pd
    from ..extraction.hybrid_extractor import HybridExtractor
    from ..core.models import Paper, Source
    # Determine input file: screening results or phase 1 search
    input_file = phase_dir / "screening_results.parquet"
    if not input_file.exists():
        input_file = phase_dir / "01_search_results.parquet"
    if not input_file.exists():
        console.print("[red]No recognised input file found in directory[/red]")
        raise typer.Exit(1)
    df = pd.read_parquet(input_file)
    console.print(f"Loaded {len(df)} papers")
    # Initialise extractor
    from ..llm.router import ModelRouter
    router = ModelRouter(local_threshold=settings.llm_local_threshold)
    extractor = HybridExtractor(
        router=router,
        min_citation_for_llm=min_citations if use_llm else 10**9,
    )
    extracted_records: List[Dict[str, Any]] = []
    async def _run_extraction() -> None:
        for _, row in df.iterrows():
            src = row.get("source", {})
            if isinstance(src, dict):
                source = Source(**src)
            else:
                source = Source(database="unknown", query="", timestamp="")
            paper = Paper(
                paper_id=row["paper_id"],
                title=row["title"],
                abstract=row.get("abstract"),
                year=row.get("year"),
                citation_count=row.get("citation_count", 0),
                external_ids=row.get("external_ids", {}),
                source=source,
            )
            data = await extractor.extract_from_paper(paper)
            data.paper_id = paper.paper_id
            extracted_records.append(data.model_dump())
    # Run extraction
    asyncio.run(_run_extraction())
    # Save output
    out_dir = output or (phase_dir / "extraction")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_df = pd.DataFrame(extracted_records)
    out_df.to_parquet(out_dir / "extracted_data.parquet", index=False)
    out_df.to_csv(out_dir / "extracted_data.csv", index=False)
    console.print(f"[green]Extraction results saved to {out_dir}[/green]")
    # Print summary
    stats = extractor.extraction_stats
    summary = Table(title="Extraction Summary")
    summary.add_column("Method", style="cyan")
    summary.add_column("Count", style="yellow", justify="right")
    summary.add_row("Regex successes", str(stats.get("regex_success", 0)))
    summary.add_row("LLM used", str(stats.get("llm_used", 0)))
    summary.add_row("Fallback", str(stats.get("fallback_used", 0)))
    console.print(summary)
    # Save LLM cost report
    try:
        cost_stats = router.get_routing_stats()
        import json as _json
        (out_dir / "llm_costs.json").write_text(_json.dumps(cost_stats, indent=2))
        console.print(f"[dim]Cost report saved to {out_dir / 'llm_costs.json'}[/dim]")
    except Exception as exc:
        logger.warning(f"Failed to save LLM cost report: {exc}")


@app.command()
def cost_report(
    session_dir: Path = typer.Argument(..., exists=True, help="Directory containing cost data"),
) -> None:
    """Display an LLM usage cost report.

    If cost data has been recorded in ``llm_costs.json`` within the
    specified directory, this command prints a summary of the cost,
    number of calls and local success rate.  Otherwise a warning is
    shown.
    """
    cost_file = session_dir / "llm_costs.json"
    if not cost_file.exists():
        console.print("[yellow]No LLM cost data found in the specified directory[/yellow]")
        raise typer.Exit(0)
    import json
    data = json.loads(cost_file.read_text())
    table = Table(title="LLM Cost Report")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_row("Total cost", f"${data.get('total_cost', 0.0):.4f}")
    table.add_row("Total calls", str(data.get('total_calls', 0)))
    table.add_row("Local success rate", f"{data.get('local_success_rate', 0.0) * 100:.1f}%")
    # Provider breakdown
    if data.get("calls_by_tier"):
        for tier, count in data["calls_by_tier"].items():
            table.add_row(f"Calls ({tier})", str(count))
    console.print(table)



if __name__ == "__main__":
    app()