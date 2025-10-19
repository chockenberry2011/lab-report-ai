"""
Test corrections API endpoint for both accepted payload formats and file persistence.

These tests verify:
1. List format: [{"field": "test_name", "new_value": "Glucose", "line_number": 1}]
2. Object format: {"corrections": [...]}
3. File persistence at /data/results/{rid}/corrections.json
4. Atomic writes and proper error handling
"""

import json
import os
from pathlib import Path
import pytest


def get_client():
    """Get test client, with graceful fallback if dependencies missing."""
    try:
        from services.api.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    except ImportError:
        return None


def test_save_corrections_list(tmp_path, monkeypatch):
    """Test corrections endpoint with list payload format"""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
        
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    rid = "abc.03_compose.debug"
    payload = [{"field": "test_name", "new_value": "Glucose", "line_number": 1}]
    
    r = client.post(f"/results/{rid}/corrections", json=payload)
    assert r.status_code == 200, r.text
    assert r.json()["saved_count"] == 1
    
    # Verify file persistence
    expected_path = tmp_path / rid / "corrections.json"
    assert expected_path.exists(), f"File not created at {expected_path}"
    
    with open(expected_path, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    assert len(file_data) == 1
    assert file_data[0]["new_value"] == "Glucose"
    
    r2 = client.get(f"/results/{rid}/corrections")
    assert r2.json()[0]["new_value"] == "Glucose"


def test_save_corrections_object(tmp_path, monkeypatch):
    """Test corrections endpoint with object payload format"""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
        
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    rid = "abc.03_compose.debug"
    payload = {"corrections": [{"field": "result_value", "new_value": "84", "line_number": 12}]}
    
    r = client.post(f"/results/{rid}/corrections", json=payload)
    assert r.status_code == 200
    assert r.json()["saved_count"] == 1

    # Verify file persistence 
    expected_path = tmp_path / rid / "corrections.json"
    assert expected_path.exists()
    
    with open(expected_path, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    assert len(file_data) == 1
    assert file_data[0]["new_value"] == "84"
    assert file_data[0]["field"] == "result_value"


def test_corrections_atomic_write_and_overwrite(tmp_path, monkeypatch):
    """Test atomic writes and that new corrections overwrite previous ones"""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
        
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    rid = "test.03_compose.debug"
    
    # First save
    payload1 = [{"field": "test_name", "new_value": "Glucose", "line_number": 1}]
    r1 = client.post(f"/results/{rid}/corrections", json=payload1)
    assert r1.status_code == 200
    assert r1.json()["saved_count"] == 1
    
    # Second save should overwrite
    payload2 = [
        {"field": "test_name", "new_value": "Cholesterol", "line_number": 2},
        {"field": "result_value", "new_value": "180", "line_number": 2}
    ]
    r2 = client.post(f"/results/{rid}/corrections", json=payload2)
    assert r2.status_code == 200
    assert r2.json()["saved_count"] == 2
    
    # Verify only latest corrections exist
    expected_path = tmp_path / rid / "corrections.json"
    with open(expected_path, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    assert len(file_data) == 2
    assert file_data[0]["new_value"] == "Cholesterol"
    assert file_data[1]["new_value"] == "180"


def test_corrections_validation_errors(tmp_path, monkeypatch):
    """Test validation errors for invalid payloads"""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
        
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    rid = "validation.03_compose.debug"
    
    # Invalid payload format
    invalid_payload = {"invalid": "format"}
    r1 = client.post(f"/results/{rid}/corrections", json=invalid_payload)
    assert r1.status_code == 400
    assert "Body must be a list of corrections" in r1.json()["detail"]
    
    # Missing required field
    invalid_correction = [{"new_value": "test", "line_number": 1}]  # missing "field"
    r2 = client.post(f"/results/{rid}/corrections", json=invalid_correction)
    assert r2.status_code == 400


def test_corrections_compatibility_routes(tmp_path, monkeypatch):
    """Test that /review prefix routes work as aliases"""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
        
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    rid = "compat.03_compose.debug"
    payload = {"corrections": [{"field": "test_name", "new_value": "Albumin", "line_number": 5}]}
    
    # Save via /review route
    r1 = client.post(f"/review/{rid}/corrections", json=payload)
    assert r1.status_code == 200
    assert r1.json()["saved_count"] == 1
    
    # Get via both routes should return same data
    r2 = client.get(f"/results/{rid}/corrections")
    r3 = client.get(f"/review/{rid}/corrections")
    assert r2.status_code == 200
    assert r3.status_code == 200
    assert r2.json()[0]["new_value"] == "Albumin"
    assert r3.json()[0]["new_value"] == "Albumin"


def test_corrections_special_result_ids(tmp_path, monkeypatch):
    """Test result IDs with dots and special characters are preserved"""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
        
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    
    # Test with full suffix preserved
    rid = "uuid-123.03_compose.debug"
    payload = [{"field": "test_name", "new_value": "Full ID Test", "line_number": 10}]
    
    r = client.post(f"/results/{rid}/corrections", json=payload)
    assert r.status_code == 200
    
    # Verify file path uses full ID
    expected_path = tmp_path / rid / "corrections.json"
    assert expected_path.exists()
    
    r2 = client.get(f"/results/{rid}/corrections")
    assert r2.status_code == 200
    assert r2.json()[0]["new_value"] == "Full ID Test"


def test_corrections_content_type_fallback(tmp_path, monkeypatch):
    """Test that corrections work with text/plain content type (fallback JSON parsing)"""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
        
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    rid = "fallback.03_compose.debug"
    payload = [{"field": "test_name", "new_value": "Fallback Test", "line_number": 15}]
    
    # Send with text/plain to trigger fallback parsing
    r = client.post(
        f"/results/{rid}/corrections",
        content=json.dumps(payload),
        headers={"Content-Type": "text/plain"}
    )
    assert r.status_code == 200
    assert r.json()["saved_count"] == 1
    
    # Verify file creation and content
    expected_path = tmp_path / rid / "corrections.json"
    assert expected_path.exists()
    
    with open(expected_path, "r", encoding="utf-8") as f:
        file_data = json.load(f)
    assert file_data[0]["new_value"] == "Fallback Test"


def test_corrections_empty_and_nonexistent(tmp_path, monkeypatch):
    """Test empty corrections and GET for nonexistent files"""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
        
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    
    # Test empty corrections
    rid_empty = "empty.03_compose.debug"
    r1 = client.post(f"/results/{rid_empty}/corrections", json=[])
    assert r1.status_code == 200
    assert r1.json()["saved_count"] == 0
    
    # Test GET for nonexistent
    rid_missing = "missing.03_compose.debug"
    r2 = client.get(f"/results/{rid_missing}/corrections")
    assert r2.status_code == 200
    assert r2.json() == []