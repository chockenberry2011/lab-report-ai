"""Test configuration and fixtures for the lab-ai project."""

import sys
import os
from pathlib import Path

# Add the project root to the Python path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "services" / "api"))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def api_client():
    """Create a test client for the FastAPI app."""
    try:
        from services.api.api.main import app
        return TestClient(app)
    except ImportError as e:
        pytest.skip(f"FastAPI dependencies not available: {e}")


@pytest.fixture
def temp_results_dir(tmp_path, monkeypatch):
    """Set up a temporary results directory for testing."""
    results_dir = tmp_path / "results"
    results_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("RESULTS_DIR", str(results_dir))
    return results_dir