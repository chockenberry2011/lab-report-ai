"""
Test results API endpoints including extracted text compatibility routes.
"""

import json
import os
from pathlib import Path
import pytest
from unittest.mock import patch, mock_open


def get_client():
    """Get test client, with graceful fallback if dependencies missing."""
    try:
        from services.api.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    except ImportError:
        return None


def test_normalize_result_id():
    """Test the normalize_result_id function directly."""
    try:
        from services.api.api.utils.ids import normalize_result_id
    except ImportError:
        pytest.skip("FastAPI dependencies not available")
    
    # Test various suffix patterns
    assert normalize_result_id("abc.03_compose.debug") == "abc"
    assert normalize_result_id("abc.debug") == "abc"
    assert normalize_result_id("abc") == "abc"
    assert normalize_result_id("uuid-1234.03_compose.debug") == "uuid-1234"
    assert normalize_result_id("test-id.debug") == "test-id"
    assert normalize_result_id("no-suffix") == "no-suffix"


def test_extracted_text_compat_with_debug_suffix(tmp_path, monkeypatch):
    """Test compatibility endpoint with .03_compose.debug suffix."""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
    
    # Set up mock data directory
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    
    # Create mock extracted text file for normalized ID
    result_id_with_suffix = "test-uuid.03_compose.debug"
    normalized_id = "test-uuid"
    
    # Mock data structure
    mock_extracted_data = {
        "lines": [
            {
                "text": "Sample Lab Report",
                "page": 1,
                "bbox": [100, 200, 300, 220],
                "confidence": 0.95,
                "role": "header"
            },
            {
                "text": "Test Name: Glucose",
                "page": 1,
                "bbox": [100, 250, 300, 270],
                "confidence": 0.90,
                "role": "test_name"
            }
        ]
    }
    
    # Create the file that would be found by the normalized ID
    test_file = outbox_dir / f"{normalized_id}.01_lines.debug.json"
    test_file.write_text(json.dumps(mock_extracted_data))
    
    # Update the OUTBOX path in the results module
    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir
    
    try:
        # Test the compatibility endpoint
        response = client.get(f"/files/{result_id_with_suffix}/extracted-text")
        assert response.status_code == 200
        
        data = response.json()
        assert "pages" in data
        assert len(data["pages"]) > 0
        assert data["pages"][0]["page"] == 1
        assert len(data["pages"][0]["lines"]) == 2
        assert data["pages"][0]["lines"][0]["text"] == "Sample Lab Report"
        
    finally:
        # Restore original OUTBOX
        results_module.OUTBOX = original_outbox


def test_extracted_text_compat_with_debug_suffix_simple(tmp_path, monkeypatch):
    """Test compatibility endpoint with .debug suffix."""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
    
    # Set up mock data directory
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    
    # Create mock extracted text file for normalized ID
    result_id_with_suffix = "test-uuid2.debug"
    normalized_id = "test-uuid2"
    
    # Mock data structure
    mock_extracted_data = {
        "lines": [
            {
                "text": "Another Lab Report",
                "page": 1,
                "bbox": [50, 100, 200, 120],
                "confidence": 0.88,
                "role": "header"
            }
        ]
    }
    
    # Create the file that would be found by the normalized ID
    test_file = outbox_dir / f"{normalized_id}.01_lines.debug.json"
    test_file.write_text(json.dumps(mock_extracted_data))
    
    # Update the OUTBOX path in the results module
    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir
    
    try:
        # Test the compatibility endpoint
        response = client.get(f"/files/{result_id_with_suffix}/extracted-text")
        assert response.status_code == 200
        
        data = response.json()
        assert "pages" in data
        assert len(data["pages"]) > 0
        assert data["pages"][0]["lines"][0]["text"] == "Another Lab Report"
        
    finally:
        # Restore original OUTBOX
        results_module.OUTBOX = original_outbox


def test_extracted_text_compat_without_suffix(tmp_path, monkeypatch):
    """Test compatibility endpoint without any debug suffix."""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
    
    # Set up mock data directory
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    
    # Create mock extracted text file for ID without suffix
    result_id_clean = "test-uuid3"
    
    # Mock data structure
    mock_extracted_data = {
        "lines": [
            {
                "text": "Clean ID Lab Report",
                "page": 1,
                "bbox": [75, 150, 250, 170],
                "confidence": 0.92,
                "role": "header"
            }
        ]
    }
    
    # Create the file that would be found by the clean ID
    test_file = outbox_dir / f"{result_id_clean}.01_lines.debug.json"
    test_file.write_text(json.dumps(mock_extracted_data))
    
    # Update the OUTBOX path in the results module
    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir
    
    try:
        # Test the compatibility endpoint
        response = client.get(f"/files/{result_id_clean}/extracted-text")
        assert response.status_code == 200
        
        data = response.json()
        assert "pages" in data
        assert len(data["pages"]) > 0
        assert data["pages"][0]["lines"][0]["text"] == "Clean ID Lab Report"
        
    finally:
        # Restore original OUTBOX
        results_module.OUTBOX = original_outbox


def test_extracted_text_compat_fallback_behavior(tmp_path, monkeypatch):
    """Test that fallback behavior works when normalized ID fails but original ID succeeds."""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
    
    # Set up mock data directory
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    
    # Create mock extracted text file only for the suffixed ID (not normalized)
    result_id_with_suffix = "fallback-test.03_compose.debug"
    
    # Mock data structure
    mock_extracted_data = {
        "lines": [
            {
                "text": "Fallback Test Report",
                "page": 1,
                "bbox": [100, 200, 300, 220],
                "confidence": 0.85,
                "role": "header"
            }
        ]
    }
    
    # Create the file using the FULL suffixed ID (not normalized)
    # This tests the fallback path
    test_file = outbox_dir / f"{result_id_with_suffix}.01_lines.debug.json"
    test_file.write_text(json.dumps(mock_extracted_data))
    
    # Update the OUTBOX path in the results module
    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir
    
    try:
        # Test the compatibility endpoint - should use fallback path
        response = client.get(f"/files/{result_id_with_suffix}/extracted-text")
        assert response.status_code == 200
        
        data = response.json()
        assert "pages" in data
        assert len(data["pages"]) > 0
        assert data["pages"][0]["lines"][0]["text"] == "Fallback Test Report"
        
    finally:
        # Restore original OUTBOX
        results_module.OUTBOX = original_outbox


def test_extracted_text_compat_not_found(tmp_path, monkeypatch):
    """Test that 404 is returned when neither normalized nor original ID files exist."""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
    
    # Set up empty mock data directory
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    
    # Update the OUTBOX path in the results module
    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir
    
    try:
        # Test the compatibility endpoint with non-existent file
        response = client.get("/files/nonexistent.03_compose.debug/extracted-text")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        
    finally:
        # Restore original OUTBOX
        results_module.OUTBOX = original_outbox
