"""
Test corrections API endpoints
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

# Add the services directory to Python path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from api.api.main import app


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set DATA_DIR environment variable
        original_data_dir = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = tmpdir
        
        # Import after setting env var
        import api.api.main
        # Force reload of DATA_DIR
        api.api.main.DATA_DIR = Path(tmpdir)
        
        yield tmpdir
        
        # Restore original
        if original_data_dir:
            os.environ["DATA_DIR"] = original_data_dir
        elif "DATA_DIR" in os.environ:
            del os.environ["DATA_DIR"]


@pytest.fixture
def client(temp_data_dir):
    """Create test client with temporary data directory"""
    return TestClient(app)


def test_corrections_save_and_get(client, temp_data_dir):
    """Test saving corrections (Shape A) and retrieving them"""
    result_id = "30dd8235-cc1c-4ef7-a9b7-99d8d8c94547.03_compose.debug"
    
    # Test payload in Shape A format
    payload = {
        "corrections": [
            {
                "op": "replace",
                "path": "panels[0].test_rows[2].result_value",
                "value": "0.78",
                "reason": "manual correction",
                "field": "result_value"
            },
            {
                "op": "replace", 
                "path": "panels[0].test_rows[2].units",
                "value": "mg/dL",
                "reason": "unit correction",
                "field": "units"
            }
        ],
        "reviewer": "ui",
        "source": "review-ui",
        "version": 1
    }
    
    # POST corrections
    response = client.post(
        f"/results/{result_id}/corrections",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    # Assert successful save
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    response_data = response.json()
    assert response_data["saved"] is True
    assert response_data["corrections_count"] == 2
    
    # GET corrections back
    get_response = client.get(f"/results/{result_id}/corrections")
    
    # Assert successful retrieval
    assert get_response.status_code == 200, f"Expected 200, got {get_response.status_code}: {get_response.text}"
    
    get_data = get_response.json()
    assert "corrections" in get_data
    assert "history" in get_data
    
    # Assert history has at least one entry
    assert len(get_data["history"]) >= 1, f"Expected history length >= 1, got {len(get_data['history'])}"
    
    # Assert the history entry contains our data
    history_entry = get_data["history"][0]
    assert history_entry["result_id"] == result_id
    assert history_entry["reviewer"] == "ui"
    assert history_entry["source"] == "review-ui"
    assert history_entry["version"] == 1
    assert len(history_entry["corrections"]) == 2
    
    # Assert flattened corrections contain our patches
    assert len(get_data["corrections"]) == 2
    
    # Check that corrections contain the expected paths
    correction_paths = [c["path"] for c in get_data["corrections"]]
    assert "panels[0].test_rows[2].result_value" in correction_paths
    assert "panels[0].test_rows[2].units" in correction_paths


def test_corrections_empty_payload(client, temp_data_dir):
    """Test that empty corrections return 400"""
    result_id = "test-empty.debug"
    
    payload = {
        "corrections": [],
        "reviewer": "ui",
        "source": "test",
        "version": 1
    }
    
    response = client.post(
        f"/results/{result_id}/corrections",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    # Should return 400 for empty corrections
    assert response.status_code == 400
    
    error_data = response.json()
    assert "empty_corrections" in str(error_data.get("detail", ""))


def test_corrections_legacy_shape_b(client, temp_data_dir):
    """Test legacy Shape B payload format"""
    result_id = "legacy-test.debug"
    
    # Test payload in Shape B (legacy) format
    payload = {
        "patches": [
            {
                "field": "result_value",
                "selector": "panels[0].test_rows[2]",
                "to": "0.78",
                "note": "manual correction"
            }
        ]
    }
    
    response = client.post(
        f"/results/{result_id}/corrections",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    # Should succeed and normalize to Shape A
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    response_data = response.json()
    assert response_data["saved"] is True
    assert response_data["corrections_count"] == 1
    
    # Verify it was normalized properly
    get_response = client.get(f"/results/{result_id}/corrections")
    get_data = get_response.json()
    
    assert len(get_data["corrections"]) == 1
    correction = get_data["corrections"][0]
    assert correction["path"] == "panels[0].test_rows[2].result_value"
    assert correction["value"] == "0.78"
    assert correction["reason"] == "manual correction"


def test_corrections_review_alias(client, temp_data_dir):
    """Test that /review/{result_id}/corrections alias works"""
    result_id = "alias-test.debug"
    
    payload = {
        "corrections": [
            {
                "op": "replace",
                "path": "panels[0].test_rows[0].test_name",
                "value": "Glucose",
                "reason": "name correction"
            }
        ],
        "reviewer": "test",
        "source": "alias-test",
        "version": 1
    }
    
    # Save via main endpoint
    client.post(f"/results/{result_id}/corrections", json=payload)
    
    # Get via alias endpoint
    response = client.get(f"/review/{result_id}/corrections")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data["corrections"]) == 1
    assert data["corrections"][0]["value"] == "Glucose"


def test_corrections_safe_filename(client, temp_data_dir):
    """Test that special characters in result_id are handled safely"""
    result_id = "test/with\\special:chars*and|more.debug"
    
    payload = {
        "corrections": [
            {
                "op": "replace",
                "path": "panels[0].test_rows[0].flag",
                "value": "H",
                "reason": "flag correction"
            }
        ],
        "reviewer": "test",
        "source": "safe-filename-test",
        "version": 1
    }
    
    response = client.post(
        f"/results/{result_id}/corrections",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    # Should succeed despite special characters
    assert response.status_code == 200
    
    # Verify file was created with safe name
    from api.api.main import safe_filename, DATA_DIR
    safe_id = safe_filename(result_id)
    corrections_file = DATA_DIR / "review" / "corrections" / f"{safe_id}.jsonl"
    assert corrections_file.exists()
    
    # Verify retrieval works
    get_response = client.get(f"/results/{result_id}/corrections")
    assert get_response.status_code == 200


def test_corrections_mixed_valid_invalid_paths(client, temp_data_dir):
    """Test posting mix of valid and invalid paths"""
    result_id = "mixed-paths-test.debug"
    
    # Test payload with mixed valid/invalid paths
    payload = {
        "items": [
            {
                "path": "lab_panels[0].test_rows[2].result_value",  # Valid dot/bracket
                "value": "85",
                "op": "replace",
                "note": "corrected value",
                "actor": "test_user"
            },
            {
                "path": "$.lab_panels[1].test_rows[0].units",  # Valid JSONPath
                "value": "mg/dL", 
                "op": "replace",
                "note": "corrected units"
            },
            {
                "path": "invalid..path[missing]bracket",  # Invalid path
                "value": "bad",
                "op": "replace",
                "note": "this should fail"
            }
        ]
    }
    
    # POST corrections
    response = client.post(
        f"/results/{result_id}/corrections",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    # Should return 200 with saved:2, bad:1
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    response_data = response.json()
    assert response_data["saved"] == 2, f"Expected saved=2, got {response_data}"
    assert response_data["bad"] == 1, f"Expected bad=1, got {response_data}"
    
    # Check JSONL file was created and has 2 lines
    from api.api.main import safe_filename, DATA_DIR
    safe_id = safe_filename(result_id)
    corrections_file = DATA_DIR / "results" / safe_id / "corrections.jsonl"
    
    assert corrections_file.exists(), f"Corrections file not found: {corrections_file}"
    
    # Read and verify JSONL content
    lines = corrections_file.read_text(encoding="utf-8").strip().split('\n')
    assert len(lines) == 2, f"Expected 2 lines in JSONL, got {len(lines)}"
    
    # Parse and verify each line
    corrections = []
    for line in lines:
        correction = json.loads(line)
        corrections.append(correction)
        
        # Verify required fields
        assert "ts" in correction
        assert "actor" in correction
        assert "op" in correction
        assert "path" in correction
        assert "raw_path" in correction
        assert "value" in correction
        assert "note" in correction
    
    # Verify the first correction (dot/bracket path)
    first_correction = corrections[0]
    assert first_correction["path"] == "/lab_panels/0/test_rows/2/result_value"
    assert first_correction["value"] == "85"
    assert first_correction["op"] == "replace"
    assert first_correction["note"] == "corrected value"
    assert first_correction["actor"] == "test_user"
    
    # Verify the second correction (JSONPath)
    second_correction = corrections[1]
    assert second_correction["path"] == "/lab_panels/1/test_rows/0/units"
    assert second_correction["value"] == "mg/dL"
    assert second_correction["op"] == "replace"
    assert second_correction["note"] == "corrected units"
    assert second_correction["actor"] == "user"  # Default actor
    
    # GET corrections and verify response
    get_response = client.get(f"/results/{result_id}/corrections")
    assert get_response.status_code == 200
    
    get_data = get_response.json()
    assert "items" in get_data
    assert len(get_data["items"]) == 2
    
    # Verify the items match what we saved
    items = get_data["items"]
    
    # First item
    assert items[0]["path"] == "/lab_panels/0/test_rows/2/result_value"
    assert items[0]["value"] == "85"
    assert items[0]["actor"] == "test_user"
    
    # Second item  
    assert items[1]["path"] == "/lab_panels/1/test_rows/0/units"
    assert items[1]["value"] == "mg/dL"
    assert items[1]["actor"] == "user"


def test_corrections_path_normalization(client, temp_data_dir):
    """Test that different path formats are normalized correctly"""
    result_id = "path-normalization.debug"
    
    payload = {
        "items": [
            {"path": "lab_panels[0].test_rows[2].units", "value": "mg/dL"},  # Dot/bracket
            {"path": "$.lab_panels[1].test_rows[0].flag", "value": "H"},     # JSONPath with $. 
            {"path": "/lab_panels/2/test_rows/1/result_value", "value": "42"} # JSON Pointer
        ]
    }
    
    response = client.post(f"/results/{result_id}/corrections", json=payload)
    assert response.status_code == 200
    
    response_data = response.json()
    assert response_data["saved"] == 3
    assert response_data["bad"] == 0
    
    # Verify all paths were normalized to JSON Pointer format
    get_response = client.get(f"/results/{result_id}/corrections")
    items = get_response.json()["items"]
    
    expected_paths = [
        "/lab_panels/0/test_rows/2/units",
        "/lab_panels/1/test_rows/0/flag", 
        "/lab_panels/2/test_rows/1/result_value"
    ]
    
    actual_paths = [item["path"] for item in items]
    assert actual_paths == expected_paths


def test_corrections_get_nonexistent(client, temp_data_dir):
    """Test GET corrections for non-existent result returns empty array"""
    result_id = "nonexistent-result.debug"
    
    response = client.get(f"/results/{result_id}/corrections")
    assert response.status_code == 200
    
    data = response.json()
    assert data == {"items": []}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])