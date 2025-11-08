"""FastAPI web application for the Systematic Review Pipeline.

This module defines the FastAPI application, mounts static files,
configures Jinja2 templates and includes the API routes. It also
provides a convenience function to launch the server via Uvicorn.
"""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from .routes import router
from ..config.settings import settings


# Create FastAPI app
app = FastAPI(
    title="Systematic Review Pipeline",
    description="Web interface for academic literature review",
    version="0.1.0",
)

# Setup templates and static files
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Include API routes
app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Dashboard home page."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Dashboard",
        },
    )


def start_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = True) -> None:
    """Start the Uvicorn web server.

    Parameters
    ----------
    host: str
        Host to bind the server to. Defaults to ``0.0.0.0``.
    port: int
        Port to listen on. Defaults to 8000.
    reload: bool
        Whether to enable auto-reload. Useful during development.
    """
    uvicorn.run(
        "srp.web.app:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    start_server()
