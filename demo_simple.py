"""
Multi-Source Supervisor Demo - OpenAlex, CrossRef, and arXiv
==============================================================

This version searches multiple databases to demonstrate intelligent deduplication.
Shows how papers appearing in multiple sources are automatically detected and merged.
"""

import asyncio
from pathlib import Path
from datetime import date, datetime
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from srp.search.orchestrator import SearchOrchestrator
from srp.dedup.deduplicator import Deduplicator
from srp.io.bibtex import BibTeXExporter

console = Console()


async def demo_simple():
    """Multi-source demo to showcase deduplication across databases"""

    # ==================== CONFIGURATION ====================
    QUERY = "deep learning medical imaging"  # Concrete query that will have duplicates
    START_DATE = date(2023, 1, 1)
    END_DATE = date(2024, 12, 31)
    LIMIT_PER_SOURCE = 15  # Search multiple sources with overlap
    SOURCES = ["openalex", "crossref", "arxiv"]  # Skip Semantic Scholar as requested
    OUTPUT_DIR = Path("demo_output")
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ==================== INTRODUCTION ====================
    console.print("\n")
    console.print(Panel.fit(
        "[bold cyan]Systematic Review Pipeline - Multi-Source Demo[/bold cyan]\n"
        "[yellow]Search → Deduplication → Export[/yellow]\n\n"
        "[dim]Searching 3 databases: OpenAlex, CrossRef, and arXiv[/dim]",
        border_style="cyan",
        padding=(1, 2)
    ))

    console.print(f"\n[bold]Query:[/bold] [cyan]{QUERY}[/cyan]")
    console.print(f"[bold]Date Range:[/bold] [cyan]{START_DATE} to {END_DATE}[/cyan]")
    console.print(f"[bold]Databases:[/bold] [cyan]{', '.join([s.title() for s in SOURCES])}[/cyan]")
    console.print(f"[bold]Limit per source:[/bold] [cyan]{LIMIT_PER_SOURCE} papers[/cyan]\n")

    # ==================== STEP 1: MULTI-SOURCE SEARCH ====================
    console.print(Panel("[bold green]STEP 1: Multi-Database Search[/bold green]",
                       border_style="green"))
    console.print("[dim]Searching across OpenAlex, CrossRef, and arXiv in parallel...[/dim]\n")

    orchestrator = SearchOrchestrator()
    all_papers = []
    source_counts = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        for source in SOURCES:
            task = progress.add_task(f"Searching {source.title()}...", total=None)
            
            try:
                papers = await orchestrator.search_source(
                    source=source,
                    query=QUERY,
                    start_date=START_DATE,
                    end_date=END_DATE,
                    limit=LIMIT_PER_SOURCE,
                    resume=False
                )
                all_papers.extend(papers)
                source_counts[source] = len(papers)
                progress.update(task, completed=True)
                console.print(f"  ✓ {source.title()}: Found [cyan]{len(papers)}[/cyan] papers")
            except KeyboardInterrupt:
                console.print(f"\n[yellow]Demo interrupted by user[/yellow]")
                raise
            except Exception as e:
                progress.update(task, completed=True)
                console.print(f"  ⚠ {source.title()}: [yellow]Skipped ({str(e)[:60]})[/yellow]")
                source_counts[source] = 0

    orchestrator.close()

    # Show search summary
    search_table = Table(title="\n📊 Search Results by Source", show_header=True, border_style="cyan")
    search_table.add_column("Database", style="cyan", width=20)
    search_table.add_column("Papers Found", justify="right", style="green")
    
    for source in SOURCES:
        count = source_counts.get(source, 0)
        search_table.add_row(source.title(), str(count))
    search_table.add_row("[bold]TOTAL", f"[bold cyan]{len(all_papers)}", style="bold")
    
    console.print()
    console.print(search_table)
    console.print()

    # Show sample papers from different sources
    if len(all_papers) >= 3:
        console.print("[bold]Sample Papers Found:[/bold]")
        for i, paper in enumerate(all_papers[:3], 1):
            source_db = paper.source.database if paper.source else "unknown"
            console.print(f"  {i}. [{source_db}] [cyan]{paper.title[:65]}...[/cyan]")
            authors_str = ', '.join([a.name for a in paper.authors[:2]]) if paper.authors else "No authors"
            console.print(f"     Authors: {authors_str}{'...' if paper.authors and len(paper.authors) > 2 else ''}")
            console.print(f"     Year: {paper.year} | Citations: {paper.citation_count}\n")

    # ==================== STEP 2: DEDUPLICATION ====================
    console.print(Panel("[bold green]STEP 2: Intelligent Deduplication[/bold green]",
                       border_style="green"))
    console.print("[dim]Using DOI matching, arXiv ID matching, and fuzzy title similarity...[/dim]\n")

    deduplicator = Deduplicator()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Detecting duplicates across sources...", total=None)
        deduped_papers, clusters = deduplicator.deduplicate(all_papers)
        progress.update(task, completed=True)

    duplicates_removed = len(all_papers) - len(deduped_papers)

    dedup_table = Table(title="\n🔍 Deduplication Results", show_header=True, border_style="cyan")
    dedup_table.add_column("Metric", style="cyan", width=30)
    dedup_table.add_column("Value", justify="right", style="green")

    dedup_table.add_row("Total Papers Retrieved", str(len(all_papers)))
    dedup_table.add_row("Duplicates Removed", f"[yellow]{duplicates_removed}[/yellow]")
    dedup_table.add_row("Unique Papers", f"[green]{len(deduped_papers)}[/green]")
    dedup_table.add_row("Duplicate Clusters Found", str(len(clusters)))

    if len(all_papers) > 0:
        dup_rate = (duplicates_removed / len(all_papers)) * 100
        dedup_table.add_row("Duplication Rate", f"[yellow]{dup_rate:.1f}%[/yellow]")

    console.print()
    console.print(dedup_table)

    # Show example duplicate cluster if available
    if clusters:
        console.print("\n[bold]Example Duplicate Cluster:[/bold]")
        cluster = clusters[0]
        console.print(f"  Canonical ID: [cyan]{cluster.canonical_id}[/cyan]")
        console.print(f"  Duplicate IDs: [yellow]{', '.join(cluster.duplicate_ids[:2])}{'...' if len(cluster.duplicate_ids) > 2 else ''}[/yellow]")
        console.print(f"  Match Type: [green]{cluster.match_type}[/green]")
        console.print(f"  Confidence: [green]{cluster.confidence:.0%}[/green]")

    console.print()

    # ==================== STEP 3: DATA QUALITY ====================
    console.print(Panel("[bold green]STEP 3: Data Quality Check[/bold green]",
                       border_style="green"))

    papers_with_doi = sum(1 for p in deduped_papers if p.doi)
    papers_with_abstract = sum(1 for p in deduped_papers if p.abstract)
    papers_with_authors = sum(1 for p in deduped_papers if p.authors)

    quality_table = Table(show_header=True, border_style="cyan")
    quality_table.add_column("Field", style="cyan")
    quality_table.add_column("Coverage", justify="right", style="green")

    total = len(deduped_papers)
    quality_table.add_row("DOI Available", f"{papers_with_doi}/{total} ({papers_with_doi/total*100:.0f}%)")
    quality_table.add_row("Abstract Available", f"{papers_with_abstract}/{total} ({papers_with_abstract/total*100:.0f}%)")
    quality_table.add_row("Authors Available", f"{papers_with_authors}/{total} ({papers_with_authors/total*100:.0f}%)")

    console.print()
    console.print(quality_table)
    console.print()

    # ==================== STEP 4: EXPORT ====================
    console.print(Panel("[bold green]STEP 4: Export Results[/bold green]",
                       border_style="green"))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV Export
    csv_file = OUTPUT_DIR / f"demo_{timestamp}.csv"
    df = pd.DataFrame({
        'Title': [p.title for p in deduped_papers],
        'Authors': ['; '.join([a.name for a in p.authors[:5]]) if p.authors else '' for p in deduped_papers],
        'Year': [p.year for p in deduped_papers],
        'DOI': [p.doi or '' for p in deduped_papers],
        'Venue': [p.venue or '' for p in deduped_papers],
        'Citations': [p.citation_count for p in deduped_papers],
        'Abstract': [p.abstract[:200] + '...' if p.abstract and len(p.abstract) > 200 else (p.abstract or '') for p in deduped_papers],
    })
    df.to_csv(csv_file, index=False, encoding='utf-8')
    console.print(f"\n  ✓ CSV exported: [cyan]{csv_file.name}[/cyan]")

    # BibTeX Export
    bibtex_file = OUTPUT_DIR / f"demo_{timestamp}.bib"
    exporter = BibTeXExporter()
    exporter.export(deduped_papers, bibtex_file)
    console.print(f"  ✓ BibTeX exported: [cyan]{bibtex_file.name}[/cyan]")

    # Parquet Export
    parquet_file = OUTPUT_DIR / f"demo_{timestamp}.parquet"
    df_full = pd.DataFrame([p.model_dump(mode="json", exclude={"raw_data"}) for p in deduped_papers])
    df_full.to_parquet(parquet_file, index=False)
    console.print(f"  ✓ Parquet exported: [cyan]{parquet_file.name}[/cyan]\n")

    # ==================== SUMMARY ====================
    console.print()
    summary = Panel(
        f"[bold green]✓ Demo Complete![/bold green]\n\n"
        f"[cyan]Databases Searched:[/cyan] {len(SOURCES)} ({', '.join([s.title() for s in SOURCES])})\n"
        f"[cyan]Total Papers Retrieved:[/cyan] {len(all_papers)}\n"
        f"[cyan]Duplicates Removed:[/cyan] [yellow]{duplicates_removed}[/yellow]\n"
        f"[cyan]Final Unique Dataset:[/cyan] [green]{len(deduped_papers)}[/green] papers\n\n"
        f"[bold]Cross-Database Deduplication:[/bold]\n"
        f"  • Same papers found in multiple sources\n"
        f"  • Automatically merged using DOI, arXiv ID, and title matching\n"
        f"  • {len(clusters)} duplicate cluster{'s' if len(clusters) != 1 else ''} detected\n\n"
        f"[bold]Time Saved vs Manual:[/bold]\n"
        f"  • Manual search & dedup: [yellow]~3-4 hours[/yellow]\n"
        f"  • Automated pipeline: [green]<3 minutes[/green] ⚡\n\n"
        f"[bold]Output Files:[/bold]\n"
        f"  📊 {csv_file.name}\n"
        f"  📚 {bibtex_file.name}\n"
        f"  💾 {parquet_file.name}\n\n"
        f"[dim]Location: {OUTPUT_DIR}[/dim]",
        title="🎉 Multi-Source Pipeline Summary",
        border_style="green",
        padding=(1, 2)
    )
    console.print(summary)

    return {
        'total_papers': len(all_papers),
        'unique_papers': len(deduped_papers),
        'duplicates_removed': duplicates_removed,
        'sources': SOURCES,
        'source_counts': source_counts,
        'csv_file': str(csv_file),
        'bibtex_file': str(bibtex_file)
    }


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  SYSTEMATIC REVIEW PIPELINE - SUPERVISOR DEMO")
    print("  Multi-Source Search: OpenAlex + CrossRef + arXiv")
    print("="*60 + "\n")

    try:
        results = asyncio.run(demo_simple())

        if results:
            print("\n" + "="*60)
            print("  ✓ Demo completed successfully!")
            print(f"  📊 Searched {len(results['sources'])} databases")
            print(f"  🎯 Found {results['total_papers']} total papers")
            print(f"  ✨ Removed {results['duplicates_removed']} duplicates")
            print(f"  ✅ Final dataset: {results['unique_papers']} unique papers")
            print(f"  📁 Check 'demo_output' folder for results")
            print("="*60 + "\n")
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user\n")
    except Exception as e:
        print(f"\n\n❌ Error: {e}\n")
        raise

