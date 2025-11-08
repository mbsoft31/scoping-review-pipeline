"""API routes for the web dashboard.

This module defines endpoints for launching searches, monitoring job
progress, browsing results, running Phase 2 analyses, viewing cache
information and exporting bibliographic data.  HTMX endpoints return
HTML snippets to update the page without full reloads.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..search.orchestrator import SearchOrchestrator
from ..dedup.deduplicator import Deduplicator
from ..enrich.citations import CitationEnricher
from ..enrich.influence import InfluenceScorer
from ..io.paths import create_output_dir, get_cache_path
from ..io.cache import SearchCache
from ..io.bibtex import BibTeXExporter

# Screening imports.  These are optional; if sentence-transformers is
# not installed the web interface will still function for search and
# analysis.  The screening endpoints will return simple error messages
# if invoked without the required dependencies.
try:
    from ..screening.screener import AutoScreener  # type: ignore
    from ..screening.semantic_matcher import SemanticMatcher  # type: ignore
    from ..screening.hitl import HITLReviewer  # type: ignore
    from ..screening.models import (
        ScreeningCriterion,
        ScreeningMode,
        ScreeningDecision,
        DomainVocabulary,
    )  # type: ignore
except Exception:  # pragma: no cover
    AutoScreener = None  # type: ignore
    SemanticMatcher = None  # type: ignore
    HITLReviewer = None  # type: ignore
    ScreeningCriterion = None  # type: ignore
    ScreeningMode = None  # type: ignore
    ScreeningDecision = None  # type: ignore
    DomainVocabulary = None  # type: ignore


router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# In-memory registry of active jobs.  Keys are job IDs and values
# contain status information that the web UI polls via HTMX.
active_jobs: Dict[str, Dict[str, object]] = {}


class SearchRequest(BaseModel):
    """Search request parameters."""

    query: str
    databases: List[str]
    start_date: str
    end_date: str
    limit: Optional[int] = None


class AnalyzeRequest(BaseModel):
    """Analysis request parameters."""

    phase1_dir: str
    citation_max_papers: int = 200
    refs_per_paper: int = 100


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request) -> HTMLResponse:
    """Render the search interface."""
    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "title": "Search Papers",
        },
    )


@router.post("/api/search/start")
async def start_search(
    search_req: SearchRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, object]:
    """Kick off a new search job in the background.

    This endpoint registers a job, creates an output directory and
    schedules ``run_search_job`` to perform the work asynchronously.
    """
    job_id = f"search_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = create_output_dir("phase1")
    # Initialise job metadata
    active_jobs[job_id] = {
        "type": "search",
        "status": "running",
        "progress": 0,
        "total": 0,
        "output_dir": str(output_dir),
        "started_at": datetime.now().isoformat(),
    }
    # Schedule background task
    background_tasks.add_task(
        run_search_job,
        job_id,
        search_req,
        output_dir,
    )
    return {
        "job_id": job_id,
        "status": "started",
        "output_dir": str(output_dir),
    }


async def run_search_job(job_id: str, search_req: SearchRequest, output_dir: Path) -> None:
    """Perform the search asynchronously and update job status."""
    try:
        orchestrator = SearchOrchestrator()
        all_papers: List[object] = []
        # Parse date strings into date objects
        start = date.fromisoformat(search_req.start_date)
        end = date.fromisoformat(search_req.end_date)
        # Search each selected database in sequence
        for db in search_req.databases:
            active_jobs[job_id]["current_db"] = db
            papers = await orchestrator.search_source(
                source=db,
                query=search_req.query,
                start_date=start,
                end_date=end,
                limit=search_req.limit,
            )
            all_papers.extend(papers)
            # Update progress counter for UI
            active_jobs[job_id]["progress"] = len(all_papers)
        # Close orchestrator (closes cache)
        orchestrator.close()
        # Persist results to disk
        if all_papers:
            df = pd.DataFrame(
                [
                    p.model_dump(mode="json", exclude={"raw_data"})
                    for p in all_papers
                ]
            )
            df.to_parquet(output_dir / "01_search_results.parquet", index=False)
            df.to_csv(output_dir / "01_search_results.csv", index=False)
        # Mark job as complete
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["total"] = len(all_papers)
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        # Record error in job metadata
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)


@router.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str) -> Dict[str, object]:
    """Return the current status of a job."""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return active_jobs[job_id]


@router.get("/api/jobs/{job_id}/progress", response_class=HTMLResponse)
async def get_job_progress_html(request: Request, job_id: str) -> HTMLResponse | str:
    """Return an HTMX snippet representing job progress."""
    if job_id not in active_jobs:
        return "<div class='text-red-500'>Job not found</div>"
    job = active_jobs[job_id]
    return templates.TemplateResponse(
        "components/progress.html",
        {
            "request": request,
            "job": job,
            "job_id": job_id,
        },
    )


@router.get("/results", response_class=HTMLResponse)
async def results_page(request: Request) -> HTMLResponse:
    """Render the results browser page.

    This page lists available Phase 1 and Phase 2 output directories.
    """
    output_dir = Path("output")
    phase1_dirs = sorted(output_dir.glob("phase1_*"), reverse=True)
    phase2_dirs = sorted(output_dir.glob("phase2_*"), reverse=True)
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "title": "Results",
            "phase1_dirs": phase1_dirs,
            "phase2_dirs": phase2_dirs,
        },
    )


@router.get("/api/results/{phase_dir:path}/papers", response_class=HTMLResponse)
async def get_papers_html(
    request: Request,
    phase_dir: str,
    page: int = 1,
    per_page: int = 20,
) -> HTMLResponse | str:
    """Return a page of papers as an HTMX component."""
    dir_path = Path(phase_dir)
    if not dir_path.exists():
        return "<div class='text-red-500'>Directory not found</div>"
    # Identify the first parquet file with papers
    parquet_files = list(dir_path.glob("*papers.parquet"))
    if not parquet_files:
        return "<div class='text-yellow-500'>No papers found</div>"
    df = pd.read_parquet(parquet_files[0])
    # Compute pagination indices
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    total_pages = (len(df) + per_page - 1) // per_page
    papers_page = df.iloc[start_idx:end_idx]
    return templates.TemplateResponse(
        "components/paper_list.html",
        {
            "request": request,
            "papers": papers_page.to_dict("records"),
            "page": page,
            "total_pages": total_pages,
            "phase_dir": phase_dir,
        },
    )


@router.get("/api/results/{phase_dir:path}/stats", response_class=JSONResponse)
async def get_stats(phase_dir: str) -> Dict[str, object]:
    """Return basic statistics for a phase output directory."""
    dir_path = Path(phase_dir)
    if not dir_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    parquet_files = list(dir_path.glob("*papers.parquet"))
    if not parquet_files:
        return {"error": "No papers found"}
    df = pd.read_parquet(parquet_files[0])
    stats: Dict[str, object] = {
        "total_papers": len(df),
        "with_doi": int(df["doi"].notna().sum()) if "doi" in df.columns else 0,
        "with_abstract": int(df["abstract"].notna().sum()) if "abstract" in df.columns else 0,
        "open_access": int(df["is_open_access"].sum()) if "is_open_access" in df.columns else 0,
        "year_range": (
            f"{int(df['year'].min())} - {int(df['year'].max())}"
            if "year" in df.columns and not df["year"].isnull().all()
            else "N/A"
        ),
        "total_citations": int(df["citation_count"].sum()) if "citation_count" in df.columns else 0,
    }
    return stats


@router.get("/analyze", response_class=HTMLResponse)
async def analyze_page(request: Request) -> HTMLResponse:
    """Render the Phase 2 analysis configuration page."""
    output_dir = Path("output")
    phase1_dirs = sorted(output_dir.glob("phase1_*"), reverse=True)
    return templates.TemplateResponse(
        "analyze.html",
        {
            "request": request,
            "title": "Analyze",
            "phase1_dirs": phase1_dirs,
        },
    )


@router.post("/api/analyze/start")
async def start_analysis(
    analyze_req: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, object]:
    """Kick off a Phase 2 analysis job."""
    job_id = f"analyze_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = create_output_dir("phase2")
    active_jobs[job_id] = {
        "type": "analyze",
        "status": "running",
        "phase": "loading",
        "output_dir": str(output_dir),
        "started_at": datetime.now().isoformat(),
    }
    background_tasks.add_task(
        run_analyze_job,
        job_id,
        analyze_req,
        output_dir,
    )
    return {
        "job_id": job_id,
        "status": "started",
        "output_dir": str(output_dir),
    }


async def run_analyze_job(job_id: str, analyze_req: AnalyzeRequest, output_dir: Path) -> None:
    """Execute the Phase 2 workflow asynchronously."""
    try:
        phase1_dir = Path(analyze_req.phase1_dir)
        # Load Phase 1 papers
        active_jobs[job_id]["phase"] = "loading"
        df = pd.read_parquet(phase1_dir / "01_search_results.parquet")
        # Convert DataFrame rows into Paper objects
        from ..core.models import Paper, Source

        papers: List[Paper] = []
        for _, row in df.iterrows():
            source_data = row.get("source", {})
            if isinstance(source_data, dict):
                source = Source(**source_data)
            else:
                source = Source(database="unknown", query="", timestamp="")
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
                    citation_count=row.get("citation_count", 0),
                    external_ids=row.get("external_ids", {}),
                    source=source,
                )
            )
        # Deduplicate
        active_jobs[job_id]["phase"] = "deduplicating"
        deduplicator = Deduplicator()
        deduped_papers, clusters = deduplicator.deduplicate(papers)
        # Save deduplicated results
        deduped_df = pd.DataFrame(
            [p.model_dump(mode="json", exclude={"raw_data"}) for p in deduped_papers]
        )
        deduped_df.to_parquet(output_dir / "02_deduped_papers.parquet", index=False)
        # Citation enrichment
        active_jobs[job_id]["phase"] = "fetching_citations"
        enricher = CitationEnricher(
            max_papers=analyze_req.citation_max_papers,
            refs_per_paper=analyze_req.refs_per_paper,
        )
        references = await enricher.fetch_references(
            deduped_papers,
            sources=["semantic_scholar"],
        )
        resolved_refs, citation_stats = enricher.resolve_citations(references, deduped_papers)
        # Save citation edges
        refs_df = pd.DataFrame([r.model_dump() for r in resolved_refs])
        refs_df.to_parquet(output_dir / "02_citation_edges.parquet", index=False)
        # Influence scoring
        active_jobs[job_id]["phase"] = "computing_influence"
        scorer = InfluenceScorer()
        influence_df = scorer.compute_influence_scores(deduped_papers, resolved_refs)
        influence_df.to_csv(output_dir / "02_seminal_papers.csv", index=False)
        # Mark job complete
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)


@router.get("/api/cache/queries", response_class=JSONResponse)
async def get_cached_queries() -> List[Dict[str, object]]:
    """Return the list of cached search queries."""
    cache_path = get_cache_path("searches")
    cache = SearchCache(cache_path)
    cursor = cache.conn.execute(
        """
        SELECT query_id, source, query_text, completed, total_papers
        FROM search_queries
        ORDER BY created_at DESC
        LIMIT 50
    """
    )
    queries: List[Dict[str, object]] = []
    for row in cursor.fetchall():
        queries.append(
            {
                "query_id": row[0],
                "source": row[1],
                "query": row[2],
                "completed": bool(row[3]),
                "total_papers": row[4],
            }
        )
    cache.close()
    return queries


@router.post("/api/export/{phase_dir:path}/bibtex")
async def export_bibtex(phase_dir: str, top_n: Optional[int] = None) -> Dict[str, str]:
    """Export papers from a phase directory to a BibTeX file.

    Optionally filters to the top ``N`` influential papers if ``top_n``
    is specified.
    """
    dir_path = Path(phase_dir)
    if not dir_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    parquet_files = list(dir_path.glob("*papers.parquet"))
    if not parquet_files:
        raise HTTPException(status_code=404, detail="No papers found")
    df = pd.read_parquet(parquet_files[0])
    from ..core.models import Paper, Source
    papers: List[Paper] = []
    for _, row in df.iterrows():
        source_data = row.get("source", {})
        if isinstance(source_data, dict):
            source = Source(**source_data)
        else:
            source = Source(database="unknown", query="", timestamp="")
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
                external_ids=row.get("external_ids", {}),
                source=source,
            )
        )
    # Filter top N papers by influence if requested
    if top_n:
        seminal_file = dir_path / "02_seminal_papers.csv"
        if seminal_file.exists():
            influence_df = pd.read_csv(seminal_file)
            top_ids = influence_df.head(top_n)["paper_id"].tolist()
            papers = [p for p in papers if p.paper_id in top_ids]
        else:
            papers = papers[:top_n]
    exporter = BibTeXExporter()
    output_path = dir_path / "references.bib"
    exporter.export(papers, output_path, top_n=None)
    return {"path": str(output_path)}

# -----------------------------------------------------------------------------
# Screening Pages and API Endpoints
# -----------------------------------------------------------------------------

@router.get("/screening", response_class=HTMLResponse)
async def screening_page(request: Request) -> HTMLResponse:
    """Render the screening configuration page.

    If the screening subsystem is not available (because optional
    dependencies like ``sentence-transformers`` are missing), a
    simple message is shown instead of the full interface.
    """
    # List available Phase 1 directories
    phase1_dirs = sorted(Path("output").glob("phase1_*"), reverse=True)
    if AutoScreener is None:
        # Show a minimal page indicating that screening is not available
        return templates.TemplateResponse(
            "components/not_implemented.html",
            {
                "request": request,
                "title": "Screening Unavailable",
                "message": "The screening module requires optional dependencies (sentence-transformers, torch).",
            },
        )
    return templates.TemplateResponse(
        "screening.html",
        {
            "request": request,
            "title": "Screen Papers",
            "phase1_dirs": phase1_dirs,
        },
    )


@router.post("/api/screening/start")
async def start_screening(request: Request, background_tasks: BackgroundTasks) -> Dict[str, object]:
    """Kick off a screening job in the background.

    Expects a JSON body with keys corresponding to the CLI ``screen``
    command (e.g. ``phase1_dir``, ``mode``, ``auto_threshold``,
    ``maybe_threshold``, ``model``, and lists of ``inclusion_criteria`` and
    ``exclusion_criteria``).  Results will be written to a new
    timestamped ``phase1.5_*`` directory.
    """
    data = await request.json()
    job_id = f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = create_output_dir("phase1.5")
    # Register job
    active_jobs[job_id] = {
        "type": "screening",
        "status": "running",
        "progress": 0,
        "total": 0,
        "phase": "initialising",
        "output_dir": str(out_dir),
        "started_at": datetime.now().isoformat(),
    }
    # If dependencies unavailable, mark job failed
    if AutoScreener is None:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = "Screening dependencies are not installed"
        return {"job_id": job_id, "status": "failed", "output_dir": str(out_dir)}
    # Schedule background job
    background_tasks.add_task(run_screening_job, job_id, data, out_dir)
    return {"job_id": job_id, "status": "started", "output_dir": str(out_dir)}


async def run_screening_job(job_id: str, config: dict, output_dir: Path) -> None:
    """Execute a screening job asynchronously and update job status."""
    try:
        from ..core.models import Paper, Source  # import here to avoid circulars
        import yaml
        import pandas as pd
        # Extract configuration
        phase1_dir = Path(config.get("phase1_dir", ""))
        if not phase1_dir.exists():
            raise ValueError(f"phase1_dir {phase1_dir} does not exist")
        # Load papers
        df = pd.read_parquet(phase1_dir / "01_search_results.parquet")
        papers: List[Paper] = []
        for _, row in df.iterrows():
            source_data = row.get("source", {})
            source = Source(**source_data) if isinstance(source_data, dict) else Source(database="unknown", query="", timestamp="")
            papers.append(Paper(
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
            ))
        active_jobs[job_id]["total"] = len(papers)
        # Parse criteria and vocabulary
        inclusion = [ScreeningCriterion(**c) for c in config.get("inclusion_criteria", [])]
        exclusion = [ScreeningCriterion(**c) for c in config.get("exclusion_criteria", [])]
        vocab_data = config.get("vocabulary")
        vocab = DomainVocabulary(**vocab_data) if vocab_data else None
        mode = ScreeningMode(config.get("mode", "auto"))
        auto_threshold = float(config.get("auto_threshold", 0.75))
        maybe_threshold = float(config.get("maybe_threshold", 0.5))
        model = config.get("model", "all-MiniLM-L6-v2")
        # Initialise matcher and screener
        matcher = SemanticMatcher(model_name=model)
        screener = AutoScreener(matcher=matcher, auto_threshold=auto_threshold, maybe_threshold=maybe_threshold)
        active_jobs[job_id]["phase"] = "screening"
        # Screen papers
        results: List[object] = []
        for idx, paper in enumerate(papers, 1):
            result = screener.screen_paper(
                paper,
                inclusion,
                exclusion,
                vocabulary=vocab,
                mode=mode,
            )
            results.append(result)
            # Update progress
            active_jobs[job_id]["progress"] = idx
        # Persist results
        import pandas as pd  # noqa: F401
        results_df = pd.DataFrame([r.model_dump() for r in results])
        results_df.to_parquet(output_dir / "screening_results.parquet", index=False)
        results_df.to_csv(output_dir / "screening_results.csv", index=False)
        # Create review queue for semi_auto and hitl modes
        if mode in [ScreeningMode.SEMI_AUTO, ScreeningMode.HITL]:
            reviewer = HITLReviewer(output_dir / "review")
            priority_ids = screener.active_learning_candidates(results, top_k=50)
            reviewer.create_review_queue(papers=papers, auto_results=results, priority_paper_ids=priority_ids)
        # Mark job completed
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)


# -----------------------------------------------------------------------------
# Data Extraction Endpoints
# -----------------------------------------------------------------------------

class ExtractionConfig(BaseModel):
    """Extraction request configuration."""
    phase_dir: str  # Directory containing papers (phase1, phase1.5 or phase2)
    use_open_access: bool = True
    use_unpaywall: bool = False
    unpaywall_email: Optional[str] = None
    extract_sample_size: bool = True
    extract_outcomes: bool = True
    extract_statistics: bool = True
    extract_methods: bool = True


@router.post("/api/extraction/start")
async def start_extraction(
    config: ExtractionConfig,
    background_tasks: BackgroundTasks,
) -> Dict[str, object]:
    """Kick off a data extraction job in the background.

    Accepts an ``ExtractionConfig`` in the request body specifying the
    input directory and extraction options.  Creates a new Phase 1.7
    output directory and schedules a job.
    """
    phase_dir = Path(config.phase_dir)
    if not phase_dir.exists():
        raise HTTPException(status_code=404, detail="Input directory not found")
    job_id = f"extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = create_output_dir("phase1.7")
    # Register job
    active_jobs[job_id] = {
        "type": "extraction",
        "status": "running",
        "phase": "loading",
        "progress": 0,
        "total": 0,
        "output_dir": str(output_dir),
        "started_at": datetime.now().isoformat(),
    }
    # Schedule background job
    background_tasks.add_task(run_extraction_job, job_id, config, output_dir)
    return {
        "job_id": job_id,
        "status": "started",
        "output_dir": str(output_dir),
    }


async def run_extraction_job(
    job_id: str,
    config: ExtractionConfig,
    output_dir: Path,
) -> None:
    """Execute the data extraction job asynchronously and update job status."""
    try:
        from ..core.models import Paper, Source  # import inside function
        from ..extraction.extractor import DataExtractor, FullTextDocument
        # Determine which parquet file to load: screening results > deduped papers > search results
        phase_dir = Path(config.phase_dir)
        df = None
        # Priority: screening results (phase1.5)
        candidate_files = [
            phase_dir / "screening_results.parquet",
            phase_dir / "02_deduped_papers.parquet",
            phase_dir / "01_search_results.parquet",
        ]
        for file in candidate_files:
            if file.exists():
                df = pd.read_parquet(file)
                break
        if df is None:
            raise ValueError("No papers file found in the specified directory")
        # Build list of Paper objects
        papers: List[Paper] = []
        for _, row in df.iterrows():
            source_data = row.get("source", {})
            source = Source(**source_data) if isinstance(source_data, dict) else Source(database="unknown", query="", timestamp="")
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
                    source=source,
                )
            )
        total = len(papers)
        active_jobs[job_id]["total"] = total
        # Create extractor
        extractor = DataExtractor()
        extracted_records: List[dict] = []
        active_jobs[job_id]["phase"] = "extracting"
        for idx, paper in enumerate(papers, 1):
            # Use abstract as proxy for full text
            text = paper.abstract or ""
            sections = {"abstract": text, "methods": text, "results": text}
            doc = FullTextDocument(
                paper_id=paper.paper_id,
                text=text,
                sections=sections,
                source="abstract",
            )
            data = extractor.extract_from_sections(doc)
            # Append extracted data as dict
            extracted_records.append(data.model_dump())
            # Update progress
            active_jobs[job_id]["progress"] = idx
        # Persist extracted data
        extracted_df = pd.DataFrame(extracted_records)
        extracted_df.to_parquet(output_dir / "03_extracted_data.parquet", index=False)
        extracted_df.to_csv(output_dir / "03_extracted_data.csv", index=False)
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["phase"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)


# -----------------------------------------------------------------------------
# Quality Assessment Endpoints
# -----------------------------------------------------------------------------

class QualityConfig(BaseModel):
    """Quality assessment request configuration."""
    phase_dir: str  # Directory containing extracted data
    tool: str = "rob2"  # rob2, robins_i, newcastle_ottawa


@router.post("/api/quality/start")
async def start_quality(
    config: QualityConfig,
    background_tasks: BackgroundTasks,
) -> Dict[str, object]:
    """Kick off a quality assessment job in the background.

    Accepts a ``QualityConfig`` with the input directory and desired tool.
    Creates a new Phase 1.8 output directory and schedules assessment.
    """
    phase_dir = Path(config.phase_dir)
    if not phase_dir.exists():
        raise HTTPException(status_code=404, detail="Input directory not found")
    job_id = f"quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = create_output_dir("phase1.8")
    active_jobs[job_id] = {
        "type": "quality",
        "status": "running",
        "phase": "loading",
        "progress": 0,
        "total": 0,
        "output_dir": str(output_dir),
        "started_at": datetime.now().isoformat(),
    }
    background_tasks.add_task(run_quality_job, job_id, config, output_dir)
    return {"job_id": job_id, "status": "started", "output_dir": str(output_dir)}


async def run_quality_job(
    job_id: str,
    config: QualityConfig,
    output_dir: Path,
) -> None:
    """Execute the quality assessment job asynchronously."""
    try:
        from ..core.models import Paper, Source  # import inside function
        from ..quality.rob_assessor import RoBAssessor, RoBTool
        # Determine file containing extracted data
        phase_dir = Path(config.phase_dir)
        df = None
        for fname in ["03_extracted_data.parquet", "03_extracted_data.csv", "screening_results.parquet"]:
            fpath = phase_dir / fname
            if fpath.exists():
                if fpath.suffix == ".parquet":
                    df = pd.read_parquet(fpath)
                else:
                    df = pd.read_csv(fpath)
                break
        if df is None:
            raise ValueError("No extracted data found in the specified directory")
        total = len(df)
        active_jobs[job_id]["total"] = total
        # Select risk of bias tool
        tool_name = config.tool.lower()
        try:
            tool = RoBTool(tool_name)  # type: ignore
        except Exception:
            tool = RoBTool.ROB2
        assessor = RoBAssessor(tool=tool)
        assessments: List[dict] = []
        active_jobs[job_id]["phase"] = "assessing"
        for idx, row in df.iterrows():
            # Convert row to Paper for identifier; use abstract as full_text
            paper_id = row.get("paper_id", str(idx))
            text = row.get("abstract", row.get("text", ""))
            # We don't have extracted data fields like randomization_method; pass None
            # Create dummy Paper for API compatibility
            paper = Paper(
                paper_id=paper_id,
                doi=row.get("doi"),
                arxiv_id=row.get("arxiv_id"),
                title=row.get("title", ""),
                abstract=text,
                authors=row.get("authors", []),
                year=row.get("year"),
                venue=row.get("venue"),
                fields_of_study=row.get("fields_of_study", []),
                citation_count=row.get("citation_count", 0),
                influential_citation_count=row.get("influential_citation_count", 0),
                is_open_access=row.get("is_open_access", False),
                open_access_pdf=row.get("open_access_pdf"),
                external_ids=row.get("external_ids", {}),
                source=Source(database="unknown", query="", timestamp=""),
            )
            assessment = assessor.assess_paper(paper, extracted_data=None, full_text=text)
            assessments.append(assessment.model_dump())
            active_jobs[job_id]["progress"] = idx + 1
        # Persist assessments
        assess_df = pd.DataFrame(assessments)
        assess_df.to_parquet(output_dir / "04_quality_assessments.parquet", index=False)
        assess_df.to_csv(output_dir / "04_quality_assessments.csv", index=False)
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["phase"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)


# -----------------------------------------------------------------------------
# PRISMA diagram endpoints
# -----------------------------------------------------------------------------

class PrismaConfig(BaseModel):
    """PRISMA diagram request configuration."""
    phase1_dir: str
    screening_dir: Optional[str] = None
    dedup_dir: Optional[str] = None


@router.get("/prisma", response_class=HTMLResponse)
async def prisma_page(request: Request) -> HTMLResponse:
    """Render the PRISMA diagram configuration page."""
    base = Path("output")
    phase1_dirs = sorted(base.glob("phase1_*"), reverse=True)
    phase15_dirs = sorted(base.glob("phase1.5_*"), reverse=True)
    phase2_dirs = sorted(base.glob("phase2_*"), reverse=True)
    return templates.TemplateResponse(
        "prisma.html",
        {
            "request": request,
            "title": "PRISMA Diagram",
            "phase1_dirs": phase1_dirs,
            "phase15_dirs": phase15_dirs,
            "phase2_dirs": phase2_dirs,
        },
    )


@router.post("/api/prisma/start")
async def start_prisma(
    config: PrismaConfig,
    background_tasks: BackgroundTasks,
) -> Dict[str, object]:
    """Kick off a PRISMA diagram generation job.

    This endpoint accepts a ``PrismaConfig`` specifying the Phase 1
    directory and optional screening and deduplication directories.
    It registers a job and schedules a background task to compute
    counts and generate a diagram.  The diagram will be saved into
    the job's output directory.
    """
    phase1_dir = Path(config.phase1_dir)
    if not phase1_dir.exists():
        raise HTTPException(status_code=404, detail="Phase 1 directory not found")
    # Validate optional dirs
    screening_dir = Path(config.screening_dir) if config.screening_dir else None
    if screening_dir is not None and not screening_dir.exists():
        raise HTTPException(status_code=404, detail="Screening directory not found")
    dedup_dir = Path(config.dedup_dir) if config.dedup_dir else None
    if dedup_dir is not None and not dedup_dir.exists():
        raise HTTPException(status_code=404, detail="Deduplication directory not found")
    job_id = f"prisma_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = create_output_dir("prisma")
    active_jobs[job_id] = {
        "type": "prisma",
        "status": "running",
        "phase": "computing",
        "output_dir": str(output_dir),
        "started_at": datetime.now().isoformat(),
        "progress": 0,
        "total": 1,
    }
    # Schedule background task
    background_tasks.add_task(
        run_prisma_job,
        job_id,
        phase1_dir,
        screening_dir,
        dedup_dir,
        output_dir,
    )
    return {"job_id": job_id, "status": "started", "output_dir": str(output_dir)}


async def run_prisma_job(
    job_id: str,
    phase1_dir: Path,
    screening_dir: Optional[Path],
    dedup_dir: Optional[Path],
    output_dir: Path,
) -> None:
    """Compute PRISMA counts and generate a diagram asynchronously."""
    try:
        from ..prisma.diagram import compute_prisma_counts, generate_prisma_diagram
        # Compute counts
        counts = compute_prisma_counts(
            phase1_dir=phase1_dir,
            screening_dir=screening_dir,
            dedup_dir=dedup_dir,
        )
        # Save counts as JSON for later reference
        counts_path = output_dir / "counts.json"
        import json
        counts_path.write_text(json.dumps(counts, indent=2))
        # Generate diagram
        diagram_path = output_dir / "prisma_diagram.png"
        generate_prisma_diagram(counts, diagram_path)
        # Update job status
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["phase"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        active_jobs[job_id]["diagram_path"] = str(diagram_path)
        active_jobs[job_id]["counts"] = counts
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)


@router.get("/api/prisma/{job_id}/image")
async def get_prisma_image(job_id: str):
    """Return the generated PRISMA diagram image for a job."""
    job = active_jobs.get(job_id)
    if not job or job.get("type") != "prisma":
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    diagram_path = job.get("diagram_path")
    if not diagram_path or not Path(diagram_path).exists():
        raise HTTPException(status_code=404, detail="Diagram not found")
    return FileResponse(diagram_path)


# -----------------------------------------------------------------------------
# Meta‑analysis endpoints
# -----------------------------------------------------------------------------
from fastapi import UploadFile, File, Form


@router.get("/meta", response_class=HTMLResponse)
async def meta_page(request: Request) -> HTMLResponse:
    """Render the meta‑analysis configuration page."""
    return templates.TemplateResponse(
        "meta.html",
        {
            "request": request,
            "title": "Meta‑Analysis",
        },
    )


@router.post("/api/meta/start")
async def start_meta(
    request: Request,
    method: str = Form("random"),
    effect_col: str = Form("effect"),
    se_col: str = Form("se"),
    study_col: str = Form("study_id"),
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
) -> Dict[str, object]:
    """Start a meta‑analysis job.

    Accepts an uploaded CSV file with effect sizes and standard errors,
    along with form parameters specifying column names and pooling method.
    Creates a job and schedules the analysis in the background.
    """
    contents = await file.read()
    import io
    csv_bytes = contents
    # Save uploaded file to a temp location within output directory
    job_id = f"meta_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = create_output_dir("meta")
    csv_path = output_dir / f"{job_id}_effects.csv"
    with open(csv_path, "wb") as f:
        f.write(csv_bytes)
    # Register job
    active_jobs[job_id] = {
        "type": "meta",
        "status": "running",
        "phase": "processing",
        "progress": 0,
        "total": 1,
        "output_dir": str(output_dir),
        "started_at": datetime.now().isoformat(),
        "effect_csv": str(csv_path),
        "method": method,
        "effect_col": effect_col,
        "se_col": se_col,
        "study_col": study_col,
    }
    # Schedule background job
    background_tasks.add_task(
        run_meta_job,
        job_id,
    )
    return {"job_id": job_id, "status": "started", "output_dir": str(output_dir)}


async def run_meta_job(job_id: str) -> None:
    """Execute the meta‑analysis asynchronously and update job status."""
    try:
        from ..meta.analyzer import MetaAnalyzer, EffectSize
        from ..meta.forest_plot import create_forest_plot
        import pandas as pd
        job = active_jobs[job_id]
        csv_path = Path(job["effect_csv"])
        method = job.get("method", "random")
        effect_col = job.get("effect_col", "effect")
        se_col = job.get("se_col", "se")
        study_col = job.get("study_col", "study_id")
        df = pd.read_csv(csv_path)
        effect_sizes: List[EffectSize] = []
        for _, row in df.iterrows():
            try:
                effect = float(row[effect_col])
                se = float(row[se_col])
            except Exception:
                continue
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
            raise ValueError("No valid effect sizes found in CSV")
        analyzer = MetaAnalyzer()
        pooled = analyzer.compute_pooled_effect(effect_sizes, method=method)
        heterogeneity = analyzer.assess_heterogeneity(effect_sizes)
        bias = analyzer.publication_bias_test(effect_sizes)
        # Generate forest plot
        df_plot = analyzer.generate_forest_plot_data(effect_sizes, pooled)
        plot_path = Path(job["output_dir"]) / f"{job_id}_forest_plot.png"
        # create_forest_plot expects list of EffectSize? But meta analyzer returns DataFrame. Use create_forest_plot directly from df_plot
        # We'll call create_forest_plot with effect sizes list and pooled dictionary
        from ..meta.forest_plot import create_forest_plot
        # Build effect size objects for plotting
        effects_to_plot: List[EffectSize] = []
        for es in effect_sizes:
            effects_to_plot.append(es)
        fig = create_forest_plot(effects_to_plot, pooled=pooled, title="Meta‑analysis Forest Plot")
        fig.savefig(plot_path)
        import json
        # Store results in job
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["phase"] = "completed"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        active_jobs[job_id]["plot_path"] = str(plot_path)
        active_jobs[job_id]["result"] = {
            "pooled": pooled,
            "heterogeneity": heterogeneity,
            "bias": bias,
            "n_studies": len(effect_sizes),
        }
    except Exception as e:
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["error"] = str(e)


@router.get("/api/meta/{job_id}/plot")
async def get_meta_plot(job_id: str):
    """Return the forest plot image for a completed meta‑analysis job."""
    job = active_jobs.get(job_id)
    if not job or job.get("type") != "meta":
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    plot_path = job.get("plot_path")
    if not plot_path or not Path(plot_path).exists():
        raise HTTPException(status_code=404, detail="Plot not found")
    return FileResponse(plot_path)


@router.get("/review", response_class=HTMLResponse)
async def review_page(request: Request) -> HTMLResponse:
    """Render the human review interface listing available screening sessions."""
    # List screening output directories
    screening_dirs = []
    for phase_dir in sorted(Path("output").glob("phase1.5_*"), reverse=True):
        review_dir = phase_dir / "review"
        if review_dir.exists() and (review_dir / "review_queue.csv").exists():
            screening_dirs.append({
                "path": str(phase_dir),
                "name": phase_dir.name,
                "created": phase_dir.stat().st_mtime,
            })
    if AutoScreener is None:
        return templates.TemplateResponse(
            "components/not_implemented.html",
            {
                "request": request,
                "title": "Review Unavailable",
                "message": "The screening module is not installed.",
            },
        )
    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "title": "Review Papers",
            "screening_dirs": screening_dirs,
        },
    )


@router.get("/api/review/{screening_dir:path}/next", response_class=JSONResponse)
async def api_get_next_for_review(screening_dir: str, n: int = 1) -> List[Dict[str, object]]:
    """Return the next N papers for review from a given screening directory."""
    dir_path = Path(screening_dir)
    if HITLReviewer is None or not dir_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    reviewer = HITLReviewer(dir_path / "review")
    return reviewer.get_next_for_review(n)


@router.post("/api/review/{screening_dir:path}/submit")
async def api_submit_review(screening_dir: str, request: Request) -> Dict[str, str]:
    """Record a human review decision via the API."""
    dir_path = Path(screening_dir)
    if HITLReviewer is None or not dir_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    data = await request.json()
    reviewer = HITLReviewer(dir_path / "review")
    reviewer.submit_review(
        paper_id=data["paper_id"],
        decision=ScreeningDecision(data["decision"]),
        reviewer=data.get("reviewer", "anonymous"),
        notes=data.get("notes"),
    )
    return {"status": "success"}


@router.get("/api/review/{screening_dir:path}/stats", response_class=JSONResponse)
async def api_review_stats(screening_dir: str) -> Dict[str, object]:
    """Return review statistics for a given screening directory."""
    dir_path = Path(screening_dir)
    if HITLReviewer is None or not dir_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found")
    reviewer = HITLReviewer(dir_path / "review")
    return reviewer.get_statistics()


@router.get("/api/screening/{screening_dir:path}/results", response_class=HTMLResponse)
async def api_screening_results_html(
    request: Request,
    screening_dir: str,
    filter_decision: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> HTMLResponse | str:
    """Return an HTML snippet containing screening results for a session."""
    dir_path = Path(screening_dir)
    results_file = dir_path / "screening_results.parquet"
    if not results_file.exists():
        return "<div class='text-yellow-500'>No screening results found</div>"
    import pandas as pd  # noqa: F401
    df = pd.read_parquet(results_file)
    # Filter by decision if provided
    if filter_decision:
        df = df[df["decision"] == filter_decision]
    # Pagination
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    total_pages = (len(df) + per_page - 1) // per_page
    results_page = df.iloc[start_idx:end_idx]
    return templates.TemplateResponse(
        "components/screening_results.html",
        {
            "request": request,
            "results": results_page.to_dict("records"),
            "page": page,
            "total_pages": total_pages,
            "screening_dir": screening_dir,
            "filter_decision": filter_decision,
        },
    )


# -----------------------------------------------------------------------------
# Additional pages for data extraction and quality assessment
# -----------------------------------------------------------------------------

@router.get("/extraction", response_class=HTMLResponse)
async def extraction_page(request: Request) -> HTMLResponse:
    """Render the data extraction configuration page."""
    # List available directories for extraction.  Prefer phase1.5 (screened) and phase2 (deduplicated) outputs, but include phase1 as fallback.
    base = Path("output")
    phase15_dirs = sorted(base.glob("phase1.5_*"), reverse=True)
    phase1_dirs = sorted(base.glob("phase1_*"), reverse=True)
    phase2_dirs = sorted(base.glob("phase2_*"), reverse=True)
    phase_dirs = phase15_dirs + phase2_dirs + phase1_dirs
    return templates.TemplateResponse(
        "extraction.html",
        {
            "request": request,
            "title": "Data Extraction",
            "phase_dirs": phase_dirs,
        },
    )


@router.get("/quality", response_class=HTMLResponse)
async def quality_page(request: Request) -> HTMLResponse:
    """Render the quality assessment configuration page."""
    # List available directories containing extracted data.  Phase1.7 outputs are produced by the extraction step.
    base = Path("output")
    phase17_dirs = sorted(base.glob("phase1.7_*"), reverse=True)
    return templates.TemplateResponse(
        "quality.html",
        {
            "request": request,
            "title": "Quality Assessment",
            "phase_dirs": phase17_dirs,
        },
    )
