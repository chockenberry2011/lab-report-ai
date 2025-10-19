"""
Tests for corrections append functionality with strict validation.

Tests the new behavior:
- Strict validation of on-disk corrections files
- Coercion of single objects to arrays
- Append and persist functionality
- Structured logging
- HTTP 422 errors for wrong file types
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.dict(os.environ, {"DATA_ROOT": tmp_dir}):
            yield Path(tmp_dir)


class TestCorrectionsAppendValidation:
    """Test corrections append functionality with strict validation."""

    def test_append_to_empty_file_single_object(self, client, temp_data_dir):
        """Test appending a single object to non-existent file (creates new)."""
        result_id = "test-result-123"

        # Send single object
        payload = {
            "field": "test_name",
            "new_value": "Glucose",
            "line_number": 15
        }

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "corrections" in data
        assert len(data["corrections"]) == 1
        assert data["corrections"][0]["field"] == "test_name"
        assert data["corrections"][0]["new_value"] == "Glucose"
        assert data["corrections"][0]["op"] == "replace"  # default
        assert "ts" in data["corrections"][0]  # timestamp added

        # Verify file was created with correct content
        corrections_path = temp_data_dir / "results" / result_id / "corrections.json"
        assert corrections_path.exists()
        with corrections_path.open() as f:
            file_data = json.load(f)
        assert isinstance(file_data, list)
        assert len(file_data) == 1

    def test_append_to_empty_file_array(self, client, temp_data_dir):
        """Test appending an array to non-existent file (creates new)."""
        result_id = "test-result-124"

        # Send array
        payload = [
            {"field": "test_name", "new_value": "Glucose", "line_number": 15},
            {"field": "result_value", "new_value": "72", "line_number": 15}
        ]

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "corrections" in data
        assert len(data["corrections"]) == 2

        # Verify both corrections are present
        fields = [c["field"] for c in data["corrections"]]
        assert "test_name" in fields
        assert "result_value" in fields

    def test_append_to_existing_valid_array(self, client, temp_data_dir):
        """Test appending to existing valid corrections array."""
        result_id = "test-result-125"

        # Create existing corrections file with valid array
        corrections_dir = temp_data_dir / "results" / result_id
        corrections_dir.mkdir(parents=True)
        corrections_path = corrections_dir / "corrections.json"

        existing_corrections = [
            {"field": "existing_field", "new_value": "existing_value", "ts": "2023-01-01T00:00:00Z"}
        ]
        with corrections_path.open("w") as f:
            json.dump(existing_corrections, f)

        # Send new correction
        payload = {"field": "test_name", "new_value": "Glucose", "line_number": 15}

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "corrections" in data
        assert len(data["corrections"]) == 2  # existing + new

        # Verify existing correction is preserved
        fields = [c["field"] for c in data["corrections"]]
        assert "existing_field" in fields
        assert "test_name" in fields

        # Verify file was updated
        with corrections_path.open() as f:
            file_data = json.load(f)
        assert len(file_data) == 2

    def test_strict_validation_wrong_type_dict(self, client, temp_data_dir):
        """Test that non-array corrections file returns HTTP 422."""
        result_id = "test-result-126"

        # Create existing corrections file with dict (wrong type)
        corrections_dir = temp_data_dir / "results" / result_id
        corrections_dir.mkdir(parents=True)
        corrections_path = corrections_dir / "corrections.json"

        wrong_type_data = {"not": "an_array"}
        with corrections_path.open("w") as f:
            json.dump(wrong_type_data, f)

        # Try to append new correction
        payload = {"field": "test_name", "new_value": "Glucose"}

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "CORRECTIONS_FILE_WRONG_TYPE"
        assert data["expected"] == "array"
        assert data["found"] == "dict"

    def test_strict_validation_wrong_type_string(self, client, temp_data_dir):
        """Test that string corrections file returns HTTP 422."""
        result_id = "test-result-127"

        # Create existing corrections file with string (wrong type)
        corrections_dir = temp_data_dir / "results" / result_id
        corrections_dir.mkdir(parents=True)
        corrections_path = corrections_dir / "corrections.json"

        with corrections_path.open("w") as f:
            json.dump("not_an_array", f)

        # Try to append new correction
        payload = {"field": "test_name", "new_value": "Glucose"}

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "CORRECTIONS_FILE_WRONG_TYPE"
        assert data["expected"] == "array"
        assert data["found"] == "str"

    def test_coerce_corrections_wrapper_format(self, client, temp_data_dir):
        """Test coercing payload with corrections wrapper."""
        result_id = "test-result-128"

        # Send payload with corrections wrapper
        payload = {
            "corrections": [
                {"field": "test_name", "new_value": "Glucose", "line_number": 15}
            ]
        }

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert len(data["corrections"]) == 1
        assert data["corrections"][0]["field"] == "test_name"

    def test_normalization_adds_defaults(self, client, temp_data_dir):
        """Test that default fields are added during normalization."""
        result_id = "test-result-129"

        payload = {"field": "test_name", "new_value": "Glucose"}

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 200
        data = response.json()
        correction = data["corrections"][0]

        # Check defaults were added
        assert correction["op"] == "replace"
        assert "ts" in correction
        assert correction["ts"].endswith("Z")  # ISO format with Z

    def test_normalization_preserves_existing_op(self, client, temp_data_dir):
        """Test that existing op field is preserved."""
        result_id = "test-result-130"

        payload = {"field": "test_name", "new_value": "Glucose", "op": "set"}

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 200
        data = response.json()
        correction = data["corrections"][0]

        # Check existing op was preserved
        assert correction["op"] == "set"

    def test_result_id_normalization(self, client, temp_data_dir):
        """Test that result IDs with suffixes are normalized."""
        result_id_with_suffix = "test-result-131.03_compose.debug"
        expected_base_id = "test-result-131"

        payload = {"field": "test_name", "new_value": "Glucose"}

        response = client.post(f"/results/{result_id_with_suffix}/corrections", json=payload)

        assert response.status_code == 200

        # Verify file was created with normalized ID
        corrections_path = temp_data_dir / "results" / expected_base_id / "corrections.json"
        assert corrections_path.exists()

    def test_invalid_payload_format(self, client, temp_data_dir):
        """Test invalid payload format returns 400."""
        result_id = "test-result-132"

        # Send invalid payload (not object, array, or wrapper)
        payload = "invalid_string"

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 400
        data = response.json()
        assert "Invalid payload format" in data["detail"]

    def test_file_system_error_handling(self, client, temp_data_dir):
        """Test proper error handling for file system errors."""
        result_id = "test-result-133"

        # Create a file where directory should be (causes permission error)
        results_dir = temp_data_dir / "results"
        results_dir.mkdir(parents=True)
        blocking_file = results_dir / result_id
        blocking_file.touch()  # Create file instead of directory

        payload = {"field": "test_name", "new_value": "Glucose"}

        response = client.post(f"/results/{result_id}/corrections", json=payload)

        assert response.status_code == 500
        assert "Failed to persist corrections" in response.json()["detail"]


class TestCorrectionsLogging:
    """Test structured logging for corrections operations."""

    @patch('api.corrections_api.log')
    def test_logging_load_ok_new_file(self, mock_log, client, temp_data_dir):
        """Test logging when creating new corrections file."""
        result_id = "test-log-1"
        payload = {"field": "test_name", "new_value": "Glucose"}

        client.post(f"/results/{result_id}/corrections", json=payload)

        # Check log calls
        load_ok_calls = [call for call in mock_log.info.call_args_list
                        if call[0][0] == "load_ok"]
        assert len(load_ok_calls) == 1

        extra = load_ok_calls[0][1]["extra"]
        assert extra["count"] == 0
        assert extra["new_file"] == True

    @patch('api.corrections_api.log')
    def test_logging_load_ok_existing_file(self, mock_log, client, temp_data_dir):
        """Test logging when loading existing valid corrections file."""
        result_id = "test-log-2"

        # Create existing file
        corrections_dir = temp_data_dir / "results" / result_id
        corrections_dir.mkdir(parents=True)
        corrections_path = corrections_dir / "corrections.json"
        existing = [{"field": "existing", "new_value": "value"}]
        with corrections_path.open("w") as f:
            json.dump(existing, f)

        payload = {"field": "test_name", "new_value": "Glucose"}
        client.post(f"/results/{result_id}/corrections", json=payload)

        # Check load_ok log
        load_ok_calls = [call for call in mock_log.info.call_args_list
                        if call[0][0] == "load_ok"]
        assert len(load_ok_calls) == 1

        extra = load_ok_calls[0][1]["extra"]
        assert extra["count"] == 1
        assert "new_file" not in extra

    @patch('api.corrections_api.log')
    def test_logging_load_wrong_type(self, mock_log, client, temp_data_dir):
        """Test logging when corrections file has wrong type."""
        result_id = "test-log-3"

        # Create file with wrong type
        corrections_dir = temp_data_dir / "results" / result_id
        corrections_dir.mkdir(parents=True)
        corrections_path = corrections_dir / "corrections.json"
        with corrections_path.open("w") as f:
            json.dump({"not": "array"}, f)

        payload = {"field": "test_name", "new_value": "Glucose"}
        client.post(f"/results/{result_id}/corrections", json=payload)

        # Check load_wrong_type log
        wrong_type_calls = [call for call in mock_log.error.call_args_list
                           if call[0][0] == "load_wrong_type"]
        assert len(wrong_type_calls) == 1

        extra = wrong_type_calls[0][1]["extra"]
        assert extra["found"] == "dict"
        assert extra["expected"] == "array"

    @patch('api.corrections_api.log')
    def test_logging_incoming_coerced_to_array(self, mock_log, client, temp_data_dir):
        """Test logging when incoming single object is coerced to array."""
        result_id = "test-log-4"
        payload = {"field": "test_name", "new_value": "Glucose"}  # Single object

        client.post(f"/results/{result_id}/corrections", json=payload)

        # Check incoming_coerced_to_array log
        coerced_calls = [call for call in mock_log.info.call_args_list
                        if call[0][0] == "incoming_coerced_to_array"]
        assert len(coerced_calls) == 1

        extra = coerced_calls[0][1]["extra"]
        assert extra["original_type"] == "dict"

    @patch('api.corrections_api.log')
    def test_logging_append_ok(self, mock_log, client, temp_data_dir):
        """Test logging when corrections are successfully appended."""
        result_id = "test-log-5"

        # Create existing file
        corrections_dir = temp_data_dir / "results" / result_id
        corrections_dir.mkdir(parents=True)
        corrections_path = corrections_dir / "corrections.json"
        existing = [{"field": "existing", "new_value": "value"}]
        with corrections_path.open("w") as f:
            json.dump(existing, f)

        payload = [{"field": "new1"}, {"field": "new2"}]
        client.post(f"/results/{result_id}/corrections", json=payload)

        # Check append_ok log
        append_calls = [call for call in mock_log.info.call_args_list
                       if call[0][0] == "append_ok"]
        assert len(append_calls) == 1

        extra = append_calls[0][1]["extra"]
        assert extra["existing_count"] == 1
        assert extra["new_count"] == 2
        assert extra["total_count"] == 3