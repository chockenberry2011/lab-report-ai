"""
Test corrections merging functionality.

Tests that saved corrections are properly merged into compose documents
when served through read endpoints.
"""

import json
import os
from pathlib import Path
import pytest
from unittest.mock import patch


def get_client():
    """Get test client, with graceful fallback if dependencies missing."""
    try:
        from services.api.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    except ImportError:
        return None


def create_mock_compose_document():
    """Create a mock compose document for testing."""
    return {
        "document_info": {
            "patient_name": "John Doe",
            "test_date": "2024-01-15"
        },
        "lab_panels": [
            {
                "panel_name": "Basic Metabolic Panel",
                "test_rows": [
                    {
                        "line_number": 5,
                        "test_name": "Glucose",
                        "result_value": "95",
                        "units": "mg/dL",
                        "reference_range": "70-99",
                        "flag": ""
                    },
                    {
                        "line_number": 6,
                        "test_name": "TSH",
                        "result_value": "152.222",
                        "units": "High",  # This is mis-parsed (should be flag)
                        "reference_range": "0.450-4.500",
                        "flag": "HIGH"   # This should be empty and units should be "uIU/mL"
                    }
                ]
            }
        ]
    }


def test_corrections_service_load_and_apply(tmp_path, monkeypatch):
    """Test the corrections service directly."""
    try:
        from services.corrections import load_corrections, apply_corrections
    except ImportError:
        pytest.skip("Corrections service not available")
    
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    
    # Create mock corrections file
    result_id = "test-123.03_compose.debug"
    corrections_dir = tmp_path / result_id
    corrections_dir.mkdir()
    
    corrections_data = [
        {
            "field": "units",
            "new_value": "uIU/mL",
            "old_value": "High",
            "line_number": 6,
            "reason": "Fix mis-parsed units/flag"
        },
        {
            "field": "flag",
            "new_value": "HIGH",
            "old_value": "",
            "line_number": 6,
            "reason": "Fix mis-parsed units/flag"
        }
    ]
    
    corrections_file = corrections_dir / "corrections.json"
    corrections_file.write_text(json.dumps(corrections_data))
    
    # Test loading corrections
    loaded_corrections = load_corrections(result_id)
    assert len(loaded_corrections) == 2
    assert "test_rows.line_6.units" in loaded_corrections
    assert "test_rows.line_6.flag" in loaded_corrections
    assert loaded_corrections["test_rows.line_6.units"] == "uIU/mL"
    assert loaded_corrections["test_rows.line_6.flag"] == "HIGH"
    
    # Test applying corrections
    compose_doc = create_mock_compose_document()
    updated_doc = apply_corrections(compose_doc, loaded_corrections)
    
    # Verify corrections were applied
    tsh_row = updated_doc["lab_panels"][0]["test_rows"][1]
    assert tsh_row["line_number"] == 6
    assert tsh_row["units"] == "uIU/mL"  # Corrected from "High"
    assert tsh_row["flag"] == "HIGH"     # Corrected value
    
    # Verify other fields unchanged
    assert tsh_row["test_name"] == "TSH"
    assert tsh_row["result_value"] == "152.222"


def test_corrections_endpoint_integration(tmp_path, monkeypatch):
    """Test the full flow: save corrections, then read with merging."""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
    
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    
    # Set up mock outbox directory and compose file
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    
    result_id = "test-integration.03_compose.debug"
    compose_file = outbox_dir / f"{result_id}.json"
    compose_document = create_mock_compose_document()
    compose_file.write_text(json.dumps(compose_document))
    
    # Update OUTBOX path in results module
    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir
    
    try:
        # Step 1: Save corrections
        corrections_payload = [
            {
                "field": "units",
                "new_value": "uIU/mL",
                "old_value": "High",
                "line_number": 6,
                "reason": "Fix TSH units mis-parse"
            },
            {
                "field": "flag", 
                "new_value": "HIGH",
                "old_value": "",
                "line_number": 6,
                "reason": "Fix TSH flag mis-parse"
            }
        ]
        
        response = client.post(f"/results/{result_id}/corrections", json=corrections_payload)
        assert response.status_code == 200
        assert response.json()["saved_count"] == 2
        
        # Step 2: Read the compose document (should include corrections)
        response = client.get(f"/results/{result_id}")
        assert response.status_code == 200
        
        updated_doc = response.json()
        
        # Verify corrections were applied
        tsh_row = None
        for panel in updated_doc["lab_panels"]:
            for test_row in panel["test_rows"]:
                if test_row["line_number"] == 6:
                    tsh_row = test_row
                    break
        
        assert tsh_row is not None, "TSH row not found"
        assert tsh_row["units"] == "uIU/mL", f"Expected units 'uIU/mL', got '{tsh_row['units']}'"
        assert tsh_row["flag"] == "HIGH", f"Expected flag 'HIGH', got '{tsh_row['flag']}'"
        
        # Step 3: Test reload (fresh request)
        response2 = client.get(f"/results/{result_id}")
        assert response2.status_code == 200
        
        reloaded_doc = response2.json()
        tsh_row_2 = None
        for panel in reloaded_doc["lab_panels"]:
            for test_row in panel["test_rows"]:
                if test_row["line_number"] == 6:
                    tsh_row_2 = test_row
                    break
        
        assert tsh_row_2 is not None
        assert tsh_row_2["units"] == "uIU/mL", "Corrections not persisted on reload"
        assert tsh_row_2["flag"] == "HIGH", "Corrections not persisted on reload"
        
    finally:
        # Restore original OUTBOX
        results_module.OUTBOX = original_outbox


def test_corrections_enhanced_endpoint(tmp_path, monkeypatch):
    """Test that the enhanced endpoint also applies corrections."""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
    
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    
    # Set up mock outbox directory and compose file
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    
    result_id = "test-enhanced.03_compose.debug"
    compose_file = outbox_dir / f"{result_id}.json"
    compose_document = create_mock_compose_document()
    compose_file.write_text(json.dumps(compose_document))
    
    # Update OUTBOX path in results module
    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir
    
    try:
        # Save corrections first
        corrections_payload = [
            {
                "field": "test_name",
                "new_value": "Thyroid Stimulating Hormone",
                "old_value": "TSH",
                "line_number": 6,
                "reason": "Expand abbreviation"
            }
        ]
        
        response = client.post(f"/results/{result_id}/corrections", json=corrections_payload)
        assert response.status_code == 200
        
        # Read via enhanced endpoint
        response = client.get(f"/results/{result_id}/enhanced")
        assert response.status_code == 200
        
        enhanced_doc = response.json()
        
        # Find the corrected test row
        tsh_row = None
        for panel in enhanced_doc["lab_panels"]:
            for test_row in panel["test_rows"]:
                if test_row["line_number"] == 6:
                    tsh_row = test_row
                    break
        
        assert tsh_row is not None
        assert tsh_row["test_name"] == "Thyroid Stimulating Hormone"
        
    finally:
        results_module.OUTBOX = original_outbox


def test_corrections_raw_endpoint_unchanged(tmp_path, monkeypatch):
    """Test that the raw endpoint does NOT apply corrections (for debugging)."""
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")
    
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    
    # Set up mock outbox directory and compose file
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()
    
    result_id = "test-raw.03_compose.debug"
    compose_file = outbox_dir / f"{result_id}.json"
    compose_document = create_mock_compose_document()
    compose_file.write_text(json.dumps(compose_document))
    
    # Update OUTBOX path in results module
    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir
    
    try:
        # Save corrections first
        corrections_payload = [
            {
                "field": "units",
                "new_value": "uIU/mL",
                "old_value": "High",
                "line_number": 6,
                "reason": "Fix TSH units"
            }
        ]
        
        response = client.post(f"/results/{result_id}/corrections", json=corrections_payload)
        assert response.status_code == 200
        
        # Read via raw endpoint (should NOT include corrections)
        response = client.get(f"/results/{result_id}/raw")
        assert response.status_code == 200
        
        raw_doc = response.json()
        
        # Verify original (uncorrected) values are returned
        tsh_row = raw_doc["lab_panels"][0]["test_rows"][1]
        assert tsh_row["line_number"] == 6
        assert tsh_row["units"] == "High"  # Original mis-parsed value
        
    finally:
        results_module.OUTBOX = original_outbox


def test_corrections_no_file_returns_empty(tmp_path, monkeypatch):
    """Test that missing corrections file returns empty dict."""
    try:
        from services.corrections import load_corrections
    except ImportError:
        pytest.skip("Corrections service not available")
    
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
    
    # Request corrections for non-existent file
    corrections = load_corrections("nonexistent.03_compose.debug")
    assert corrections == {}


def test_corrections_preserves_original_structure():
    """Test that applying corrections preserves the original document structure."""
    try:
        from services.corrections import apply_corrections
    except ImportError:
        pytest.skip("Corrections service not available")
    
    original_doc = create_mock_compose_document()
    corrections = {
        "test_rows.line_5.result_value": "100"  # Glucose value correction
    }
    
    updated_doc = apply_corrections(original_doc, corrections)
    
    # Verify structure is preserved
    assert "document_info" in updated_doc
    assert "lab_panels" in updated_doc
    assert len(updated_doc["lab_panels"]) == 1
    assert len(updated_doc["lab_panels"][0]["test_rows"]) == 2
    
    # Verify correction was applied
    glucose_row = updated_doc["lab_panels"][0]["test_rows"][0]
    assert glucose_row["result_value"] == "100"
    
    # Verify other values unchanged
    assert glucose_row["test_name"] == "Glucose"
    assert glucose_row["units"] == "mg/dL"