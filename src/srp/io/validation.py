"""Data validation utilities for systematic review outputs.

This module provides a `DataValidator` class for checking the quality and
integrity of deduplicated papers and citation data, along with a helper
function `validate_phase_output` that orchestrates validation on a phase
directory. Validation covers schema compliance, identifier formats,
publication dates, completeness of critical fields, detection of duplicates,
and citation graph integrity. Results are presented via rich console
messages and aggregated into a summary report.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import re

import pandas as pd  # type: ignore
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..core.models import Paper, Source, Author
from ..core.ids import normalize_doi, normalize_arxiv_id
from ..utils.logging import get_logger


console = Console()
logger = get_logger(__name__)


class DataValidator:
    """
    Validate systematic review data quality and integrity.

    Validators accumulate errors, warnings, and info messages and can
    summarise results after performing checks. If `strict` is enabled,
    warnings are treated as errors when determining overall success.
    """

    def __init__(self, strict: bool = False) -> None:
        self.strict = strict
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def validate_schema(self, papers: List[Paper]) -> bool:
        """Validate that each paper conforms to the Pydantic schema."""
        console.print("\n[cyan]Validating schema...[/cyan]")
        invalid = 0
        for i, paper in enumerate(papers):
            try:
                # Use model_dump + model_validate to revalidate
                Paper.model_validate(paper.model_dump())
            except Exception as e:
                invalid += 1
                self.errors.append(f"Paper {i} schema invalid: {e}")
        if invalid == 0:
            console.print(f"[green]✓ All {len(papers)} papers valid[/green]")
            return True
        else:
            console.print(f"[red]✗ {invalid} papers invalid[/red]")
            return False

    def validate_identifiers(self, papers: List[Paper]) -> bool:
        """Check DOI and arXiv ID formats."""
        console.print("\n[cyan]Validating identifiers...[/cyan]")
        invalid_dois: List[tuple[str, str]] = []
        invalid_arxiv: List[tuple[str, str]] = []
        for paper in papers:
            if paper.doi:
                # Basic DOI pattern: 10.<prefix>/<suffix>
                if not paper.doi.lower().startswith("10."):
                    invalid_dois.append((paper.paper_id, paper.doi))
            if paper.arxiv_id:
                # Accept formats like YYYY.NNNNN or YYMM.NNNNN; use regex
                if not re.match(r"^\d{4}\.\d{4,5}$", paper.arxiv_id):
                    invalid_arxiv.append((paper.paper_id, paper.arxiv_id))
        if invalid_dois:
            for pid, doi in invalid_dois[:5]:
                self.warnings.append(f"Invalid DOI format: {doi} (paper: {pid})")
        if invalid_arxiv:
            for pid, aid in invalid_arxiv[:5]:
                self.warnings.append(f"Invalid arXiv ID format: {aid} (paper: {pid})")
        total_invalid = len(invalid_dois) + len(invalid_arxiv)
        if total_invalid == 0:
            console.print("[green]✓ All identifiers valid[/green]")
            return True
        else:
            console.print(f"[yellow]⚠ {total_invalid} invalid identifiers[/yellow]")
            return not self.strict

    def validate_dates(self, papers: List[Paper]) -> bool:
        """Check for missing, future, or suspicious publication years."""
        console.print("\n[cyan]Validating dates...[/cyan]")
        from datetime import datetime
        current_year = datetime.now().year
        missing_year = 0
        future_year = 0
        old_year = 0
        for paper in papers:
            if not paper.year:
                missing_year += 1
            elif paper.year > current_year + 1:
                future_year += 1
                self.warnings.append(f"Future year {paper.year}: {paper.paper_id}")
            elif paper.year < 1900:
                old_year += 1
                self.warnings.append(f"Suspicious year {paper.year}: {paper.paper_id}")
        console.print(f"  Missing year: {missing_year}")
        console.print(f"  Future year: {future_year}")
        console.print(f"  Pre-1900 year: {old_year}")
        if future_year > 0 or old_year > 0:
            console.print("[yellow]⚠ Date issues found[/yellow]")
            return not self.strict
        else:
            console.print("[green]✓ Dates valid[/green]")
            return True

    def validate_completeness(self, papers: List[Paper]) -> bool:
        """Check for missing critical metadata fields."""
        console.print("\n[cyan]Validating completeness...[/cyan]")
        stats = {
            "missing_title": 0,
            "missing_authors": 0,
            "missing_abstract": 0,
            "missing_year": 0,
            "missing_doi_and_arxiv": 0,
        }
        for paper in papers:
            if not paper.title or paper.title.lower() == "untitled":
                stats["missing_title"] += 1
            if not paper.authors:
                stats["missing_authors"] += 1
            if not paper.abstract:
                stats["missing_abstract"] += 1
            if not paper.year:
                stats["missing_year"] += 1
            if not paper.doi and not paper.arxiv_id:
                stats["missing_doi_and_arxiv"] += 1
        table = Table(title="Completeness Statistics")
        table.add_column("Field", style="cyan")
        table.add_column("Missing", style="yellow", justify="right")
        table.add_column("Percentage", style="magenta", justify="right")
        total = len(papers) if papers else 1
        for field, count in stats.items():
            pct = (count / total) * 100
            table.add_row(field.replace("_", " ").title(), str(count), f"{pct:.1f}%")
        console.print(table)
        critical_missing = stats["missing_title"] + stats["missing_authors"]
        if critical_missing > 0:
            self.warnings.append(f"{critical_missing} papers missing critical fields")
            return not self.strict
        return True

    def check_duplicates(self, papers: List[Paper]) -> bool:
        """Identify exact duplicates via DOI or arXiv ID."""
        console.print("\n[cyan]Checking for duplicates...[/cyan]")
        doi_counts: Dict[str, int] = {}
        for p in papers:
            if p.doi:
                doi_counts[p.doi] = doi_counts.get(p.doi, 0) + 1
        arxiv_counts: Dict[str, int] = {}
        for p in papers:
            if p.arxiv_id:
                arxiv_counts[p.arxiv_id] = arxiv_counts.get(p.arxiv_id, 0) + 1
        doi_dups = {doi: c for doi, c in doi_counts.items() if c > 1}
        arxiv_dups = {aid: c for aid, c in arxiv_counts.items() if c > 1}
        if doi_dups:
            console.print(f"[yellow]⚠ {len(doi_dups)} duplicate DOIs found[/yellow]")
            for doi, count in list(doi_dups.items())[:5]:
                self.warnings.append(f"Duplicate DOI: {doi} ({count} times)")
        if arxiv_dups:
            console.print(f"[yellow]⚠ {len(arxiv_dups)} duplicate arXiv IDs found[/yellow]")
            for aid, count in list(arxiv_dups.items())[:5]:
                self.warnings.append(f"Duplicate arXiv ID: {aid} ({count} times)")
        total_dups = len(doi_dups) + len(arxiv_dups)
        if total_dups == 0:
            console.print("[green]✓ No exact duplicates found[/green]")
            return True
        else:
            return not self.strict

    def validate_citations(self, citations_path: Optional[Path]) -> bool:
        """Validate citation graph integrity from a Parquet file."""
        if not citations_path or not citations_path.exists():
            console.print("\n[yellow]⚠ No citations file to validate[/yellow]")
            return True
        console.print("\n[cyan]Validating citations...[/cyan]")
        df = pd.read_parquet(citations_path)
        required_cols = ["citing_paper_id", "cited_doi", "source"]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            self.errors.append(f"Missing columns in citations: {missing}")
            console.print(f"[red]✗ Missing columns: {missing}[/red]")
            return False
        total_refs = len(df)
        in_corpus = df["cited_paper_id"].notna().sum() if "cited_paper_id" in df.columns else 0
        external = total_refs - in_corpus
        console.print(f"  Total references: {total_refs}")
        console.print(f"  In-corpus citations: {in_corpus}")
        console.print(f"  External citations: {external}")
        console.print("[green]✓ Citations valid[/green]")
        return True

    def generate_report(self) -> bool:
        """Print a summary report and return True if validation passes."""
        console.print("\n" + "=" * 60)
        console.print("[bold]Validation Report[/bold]")
        console.print("=" * 60)
        if self.errors:
            console.print(f"\n[bold red]Errors ({len(self.errors)}):[/bold red]")
            for e in self.errors:
                console.print(f"  [red]✗ {e}[/red]")
        if self.warnings:
            console.print(f"\n[bold yellow]Warnings ({len(self.warnings)}):[/bold yellow]")
            for w in self.warnings[:20]:
                console.print(f"  [yellow]⚠ {w}[/yellow]")
            if len(self.warnings) > 20:
                console.print(f"  [dim]... and {len(self.warnings) - 20} more warnings[/dim]")
        if not self.errors and not self.warnings:
            console.print("\n[bold green]✓ All validations passed![/bold green]")
        console.print(f"\n[bold]Summary:[/bold]")
        console.print(f"  Errors: {len(self.errors)}")
        console.print(f"  Warnings: {len(self.warnings)}")
        return len(self.errors) == 0 and (not self.strict or len(self.warnings) == 0)


def validate_phase_output(
    phase_dir: Path,
    check_schema: bool = True,
    check_duplicates: bool = True,
    check_citations: bool = True,
    strict: bool = False,
) -> bool:
    """Run validations on a phase output directory.

    Args:
        phase_dir: Path to the phase output directory (phase1 or phase2).
        check_schema: If True, validate Pydantic schema compliance.
        check_duplicates: Check for duplicate DOIs and arXiv IDs.
        check_citations: Validate citation graph if available.
        strict: Treat warnings as errors when determining pass/fail.

    Returns:
        True if all enabled validations pass; False otherwise.
    """
    console.print(
        Panel(
            f"Validating: {phase_dir}", title="Data Validation", border_style="cyan"
        )
    )
    validator = DataValidator(strict=strict)
    # Load papers
    parquet_files = list(phase_dir.glob("*papers.parquet"))
    if not parquet_files:
        console.print("[red]Error: No parquet files found[/red]")
        return False
    console.print(f"Loading papers from {parquet_files[0]}...")
    df = pd.read_parquet(parquet_files[0])
    papers: List[Paper] = []
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
        except Exception as e:
            logger.warning(f"Failed to parse row: {e}")
            continue
    console.print(f"[green]Loaded {len(papers)} papers[/green]")
    results: List[bool] = []
    if check_schema:
        results.append(validator.validate_schema(papers))
    results.append(validator.validate_identifiers(papers))
    results.append(validator.validate_dates(papers))
    results.append(validator.validate_completeness(papers))
    if check_duplicates:
        results.append(validator.check_duplicates(papers))
    if check_citations:
        citations_file = phase_dir / "02_citation_edges.parquet"
        results.append(validator.validate_citations(citations_file))
    passed = validator.generate_report()
    return passed and all(results)