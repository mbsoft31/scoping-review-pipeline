# Web Module

The **web** module exposes the Systematic Review Pipeline via a FastAPI web server and serves HTML pages rendered with Jinja2.  The goal of the web dashboard is to make the pipeline accessible to users without writing code.

## App entrypoint

[`app.py`](../../src/srp/web/app.py) creates the FastAPI application, configures Jinja2 templates and static file serving, and mounts API routes from `routes.py`.  The `start_server()` function launches Uvicorn with configurable host, port and reload options.  From the CLI, you can run:

```bash
srp serve --host 0.0.0.0 --port 8000 --reload
```

This starts the server and makes the dashboard available at `http://localhost:8000/`.

## Routes

The majority of API and page logic lives in [`routes.py`](../../src/srp/web/routes.py).  Key routes include:

- `GET /`: Renders the home page (`index.html`).
- `GET /search`: Presents a form for composing search queries.
- `POST /api/search`: Accepts a search request and initiates Phase 1 via the orchestrator.  Returns JSON containing a job ID.
- `GET /results/{job_id}`: Shows a listing of search results for a completed job.
- `POST /api/screen`: Initiates screening of a result set.  Returns a job ID.
- `GET /screening/{job_id}`: Displays screening results and progress for a job.
- `GET /review/{job_id}` / `POST /api/review`: Serves pages and endpoints for human review of uncertain papers.
- `GET /extraction`: Provides a page with controls for configuring full‑text retrieval and extraction (Phase 1.7).  The associated API endpoints are placeholders to be implemented.
- `GET /quality`: Allows users to choose a risk‑of‑bias tool and run assessments (Phase 1.8).  API endpoints are pending implementation.
- `GET /prisma`: Would display a generated PRISMA diagram.
- `GET /meta`: Placeholder page for meta‑analysis results.  API integration remains to be wired.

### Templates and Components

HTML templates are stored under `src/srp/web/templates/` and are written using Jinja2 with [HTMX](https://htmx.org/) and [Alpine.js](https://alpinejs.dev/) to provide reactive behaviour.  Notable templates include:

- `base.html`: Base layout with a navigation bar and slots for page content.
- `index.html`, `search.html`, `results.html`: Pages for search and result display.
- `screening.html`, `review.html`: Interfaces for screening and human review.
- `extraction.html`, `quality.html`: Interfaces for data extraction and risk‑of‑bias assessment.
- Components under `templates/components/` such as `progress.html`, `paper_list.html` and `screening_results.html` render reusable parts of the UI.

### Static assets

JavaScript and CSS files are served from the `static/` directory.  The dashboard uses Tailwind CSS for styling and minimal custom JavaScript (Alpine.js) for interactivity.

## Extending the Web UI

Additional functionality such as data extraction, quality assessment, PRISMA and meta‑analysis can be integrated by adding endpoints in `routes.py` and corresponding templates.  The asynchronous nature of FastAPI allows long‑running tasks to be offloaded to background workers (see `worker.py` for an example worker entrypoint).  Authentication, user management and real‑time updates (e.g. via WebSockets) are areas for future improvement.