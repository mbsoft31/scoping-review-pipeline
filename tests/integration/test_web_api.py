"""Integration tests for the SRP web API.

These tests spin up a TestClient using FastAPI and verify that
various endpoints return expected responses and status codes.
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import shutil

from srp.web.app import app


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def temp_output():
    """Create a temporary output directory for writing test data."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


def test_homepage(client):
    """Verify the homepage loads and contains expected text."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Systematic Review Pipeline" in response.text


def test_search_page(client):
    """Verify the search page loads."""
    response = client.get("/search")
    assert response.status_code == 200
    assert "Search Academic Papers" in response.text


def test_results_page(client):
    """Verify the results page loads."""
    response = client.get("/results")
    assert response.status_code == 200


def test_analyze_page(client):
    """Verify the analyze page loads."""
    response = client.get("/analyze")
    assert response.status_code == 200


def test_api_cache_queries(client):
    """Ensure the cached queries endpoint returns a list."""
    response = client.get("/api/cache/queries")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_search_api_endpoint(client):
    """Test launching a search job via the API endpoint."""
    search_data = {
        "query": "test query",
        "databases": ["openalex"],
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "limit": 5,
    }
    response = client.post("/api/search/start", json=search_data)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data.get("status") == "started"


def test_stats_api_nonexistent_dir(client):
    """Requesting stats for a missing directory should return 404."""
    response = client.get("/api/results/nonexistent/stats")
    assert response.status_code == 404