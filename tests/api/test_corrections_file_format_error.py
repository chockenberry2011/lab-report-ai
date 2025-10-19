"""
Tests for corrections file format error handling.

Tests that HTTP 422 is returned with proper error structure when corrections
files contain invalid formats (objects instead of arrays).
"""

import json
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

# Add the services/api directory to the path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/api"))

from api.main import app
from api.exceptions import CorrectionsFileFormatError


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with patch.dict(os.environ, {"DATA_ROOT": tmp_dir}):
            yield Path(tmp_dir)


class TestCorrectionsFileFormatError:
    """Test the custom CorrectionsFileFormatError exception."""

    def test_exception_creation(self):
        """Test creating the exception with all parameters."""
        error = CorrectionsFileFormatError(
            result_id="test123",
            file_path="/data/results/test123/corrections.json",
            expected_type="array",
            found_type="dict"
        )

        assert error.result_id == "test123"
        assert error.file_path == "/data/results/test123/corrections.json"
        assert error.expected_type == "array"
        assert error.found_type == "dict"
        assert "test123" in str(error)
        assert "array" in str(error)
        assert "dict" in str(error)

    def test_exception_default_message(self):
        """Test exception with default message construction."""
        error = CorrectionsFileFormatError(
            result_id="abc456",
            file_path="/path/to/file.json"
        )

        message = str(error)
        assert "abc456" in message
        assert "/path/to/file.json" in message
        assert "expected array, found object" in message

    def test_exception_custom_message(self):
        """Test exception with custom message."""
        custom_message = "Custom error message for testing"
        error = CorrectionsFileFormatError(
            result_id="test789",
            file_path="/test/path",
            message=custom_message
        )

        assert str(error) == custom_message

    def test_to_http_response_body(self):
        """Test conversion to HTTP response body."""
        error = CorrectionsFileFormatError(
            result_id="test123",
            file_path="/data/results/test123/corrections.json",
            expected_type="array",
            found_type="dict"
        )

        response_body = error.to_http_response_body()

        expected_fields = {
            "error": "CORRECTIONS_FILE_WRONG_TYPE",
            "expected": "array",
            "found": "dict",
            "result_id": "test123",
            "fix": "Run corrections migration or delete the file to allow recreation as an array"
        }

        for field, expected_value in expected_fields.items():
            assert field in response_body
            assert response_body[field] == expected_value

        assert "message" in response_body
        assert isinstance(response_body["message"], str)


class TestResultsAPIErrorHandling:
    """Test that the results API properly handles corrections file format errors."""

    def create_test_result_file(self, temp_data_dir: Path, job_id: str):
        """Helper to create a test result file."""
        outbox_dir = temp_data_dir / "outbox"
        outbox_dir.mkdir(parents=True, exist_ok=True)

        result_file = outbox_dir / f"{job_id}.json"
        test_result = {
            "lab_panels": [
                {
                    "test_rows": [
                        {
                            "test_name": "Glucose",
                            "result_value": "95",
                            "units": "mg/dL",
                            "line_number": 10
                        }
                    ]
                }
            ]
        }

        with result_file.open("w") as f:
            json.dump(test_result, f)

        return result_file

    def create_invalid_corrections_file(self, temp_data_dir: Path, result_id: str, data):
        """Helper to create a corrections file with invalid format."""
        results_dir = temp_data_dir / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        corrections_dir = results_dir / result_id
        corrections_dir.mkdir(parents=True, exist_ok=True)

        corrections_file = corrections_dir / "corrections.json"
        with corrections_file.open("w") as f:
            json.dump(data, f)

        return corrections_file

    @patch.dict(os.environ, {"RESULTS_DIR": "/tmp/test-results"})
    def test_get_result_with_invalid_corrections_object(self, client, temp_data_dir):
        """Test GET /results/{id} returns 422 for object-format corrections file."""
        job_id = "test-object-corrections"

        # Create test result file
        self.create_test_result_file(temp_data_dir, job_id)

        # Create invalid corrections file (object instead of array)
        invalid_corrections = {
            "field": "test_name",
            "new_value": "Updated Glucose",
            "old_value": "Glucose",
            "line_number": 10
        }
        self.create_invalid_corrections_file(temp_data_dir, job_id, invalid_corrections)

        # Mock the outbox and results directories
        with patch('api.results.OUTBOX', temp_data_dir / "outbox"), \
             patch('api.results.RESULTS_DIR', temp_data_dir / "results"):

            response = client.get(f"/results/{job_id}")

        assert response.status_code == 422
        error_data = response.json()

        # Verify error structure
        assert error_data["error"] == "CORRECTIONS_FILE_WRONG_TYPE"
        assert error_data["expected"] == "array"
        assert error_data["found"] == "dict"
        assert error_data["result_id"] == job_id
        assert "Run corrections migration" in error_data["fix"]

    @patch.dict(os.environ, {"RESULTS_DIR": "/tmp/test-results"})
    def test_get_enhanced_result_with_invalid_corrections_object(self, client, temp_data_dir):
        """Test GET /results/{id}/enhanced returns 422 for object-format corrections file."""
        job_id = "test-enhanced-object-corrections"

        # Create test result file
        self.create_test_result_file(temp_data_dir, job_id)

        # Create invalid corrections file (object instead of array)
        invalid_corrections = {
            "field": "result_value",
            "new_value": "100",
            "old_value": "95",
            "line_number": 10
        }
        self.create_invalid_corrections_file(temp_data_dir, job_id, invalid_corrections)

        # Mock the outbox and results directories
        with patch('api.results.OUTBOX', temp_data_dir / "outbox"), \
             patch('api.results.RESULTS_DIR', temp_data_dir / "results"):

            response = client.get(f"/results/{job_id}/enhanced")

        assert response.status_code == 422
        error_data = response.json()

        # Verify error structure
        assert error_data["error"] == "CORRECTIONS_FILE_WRONG_TYPE"
        assert error_data["expected"] == "array"
        assert error_data["found"] == "dict"
        assert error_data["result_id"] == job_id
        assert "delete the file to allow recreation as an array" in error_data["fix"]

    @patch.dict(os.environ, {"RESULTS_DIR": "/tmp/test-results"})
    def test_get_result_with_invalid_corrections_string(self, client, temp_data_dir):
        """Test GET /results/{id} returns 422 for string-format corrections file."""
        job_id = "test-string-corrections"

        # Create test result file
        self.create_test_result_file(temp_data_dir, job_id)

        # Create invalid corrections file (string instead of array)
        invalid_corrections = "not_an_array_or_object"
        self.create_invalid_corrections_file(temp_data_dir, job_id, invalid_corrections)

        # Mock the outbox and results directories
        with patch('api.results.OUTBOX', temp_data_dir / "outbox"), \
             patch('api.results.RESULTS_DIR', temp_data_dir / "results"):

            response = client.get(f"/results/{job_id}")

        assert response.status_code == 422
        error_data = response.json()

        # Verify error structure
        assert error_data["error"] == "CORRECTIONS_FILE_WRONG_TYPE"
        assert error_data["expected"] == "array"
        assert error_data["found"] == "str"  # string type in Python
        assert error_data["result_id"] == job_id

    @patch.dict(os.environ, {"RESULTS_DIR": "/tmp/test-results"})
    def test_get_result_with_valid_corrections_array(self, client, temp_data_dir):
        """Test GET /results/{id} succeeds with valid array-format corrections."""
        job_id = "test-valid-corrections"

        # Create test result file
        self.create_test_result_file(temp_data_dir, job_id)

        # Create valid corrections file (array format)
        valid_corrections = [
            {
                "field": "test_name",
                "new_value": "Updated Glucose",
                "old_value": "Glucose",
                "line_number": 10
            }
        ]
        self.create_invalid_corrections_file(temp_data_dir, job_id, valid_corrections)

        # Mock the outbox and results directories
        with patch('api.results.OUTBOX', temp_data_dir / "outbox"), \
             patch('api.results.RESULTS_DIR', temp_data_dir / "results"):

            response = client.get(f"/results/{job_id}")

        # Should succeed with 200
        assert response.status_code == 200
        result_data = response.json()
        assert "lab_panels" in result_data

    @patch.dict(os.environ, {"RESULTS_DIR": "/tmp/test-results"})
    def test_get_result_with_no_corrections_file(self, client, temp_data_dir):
        """Test GET /results/{id} succeeds when no corrections file exists."""
        job_id = "test-no-corrections"

        # Create test result file
        self.create_test_result_file(temp_data_dir, job_id)

        # Don't create corrections file

        # Mock the outbox and results directories
        with patch('api.results.OUTBOX', temp_data_dir / "outbox"), \
             patch('api.results.RESULTS_DIR', temp_data_dir / "results"):

            response = client.get(f"/results/{job_id}")

        # Should succeed with 200
        assert response.status_code == 200
        result_data = response.json()
        assert "lab_panels" in result_data

    def test_get_result_nonexistent_job(self, client, temp_data_dir):
        """Test GET /results/{id} returns 404 for nonexistent job."""
        job_id = "nonexistent-job"

        # Mock the outbox directory (empty)
        with patch('api.results.OUTBOX', temp_data_dir / "outbox"):
            response = client.get(f"/results/{job_id}")

        assert response.status_code == 404
        assert "Result not found" in response.json()["detail"]

    @patch.dict(os.environ, {"RESULTS_DIR": "/tmp/test-results"})
    def test_result_id_normalization_with_invalid_corrections(self, client, temp_data_dir):
        """Test that result ID normalization works with invalid corrections files."""
        base_job_id = "test-normalization"
        suffixed_job_id = f"{base_job_id}.03_compose.debug"

        # Create test result file with base ID
        self.create_test_result_file(temp_data_dir, suffixed_job_id)

        # Create invalid corrections file for base ID (normalization strips suffix)
        invalid_corrections = {"field": "test_name", "new_value": "Updated"}
        self.create_invalid_corrections_file(temp_data_dir, base_job_id, invalid_corrections)

        # Mock the outbox and results directories
        with patch('api.results.OUTBOX', temp_data_dir / "outbox"), \
             patch('api.results.RESULTS_DIR', temp_data_dir / "results"):

            response = client.get(f"/results/{suffixed_job_id}")

        assert response.status_code == 422
        error_data = response.json()

        # Verify the normalized ID is used in error reporting
        assert error_data["result_id"] == base_job_id  # Normalized ID


class TestErrorResponseFormat:
    """Test the exact format of error responses for UI integration."""

    def test_error_response_has_required_fields(self):
        """Test that error response includes all fields needed by UI."""
        error = CorrectionsFileFormatError(
            result_id="ui-test",
            file_path="/data/results/ui-test/corrections.json",
            expected_type="array",
            found_type="dict"
        )

        response_body = error.to_http_response_body()

        # Required fields for UI error handling
        required_fields = ["error", "message", "expected", "found", "result_id", "fix"]

        for field in required_fields:
            assert field in response_body, f"Missing required field: {field}"

        # Verify specific values
        assert response_body["error"] == "CORRECTIONS_FILE_WRONG_TYPE"
        assert "array" in response_body["expected"]
        assert "dict" in response_body["found"]
        assert "migration" in response_body["fix"].lower()

    def test_actionable_fix_guidance(self):
        """Test that fix guidance is actionable and specific."""
        error = CorrectionsFileFormatError(
            result_id="guidance-test",
            file_path="/test/path",
            found_type="dict"
        )

        response_body = error.to_http_response_body()
        fix_message = response_body["fix"]

        # Should mention specific actions
        assert "migration" in fix_message.lower()
        assert "delete" in fix_message.lower()
        assert "array" in fix_message.lower()

        # Should be actionable (contains verbs)
        action_verbs = ["run", "delete", "allow"]
        assert any(verb in fix_message.lower() for verb in action_verbs)

    def test_error_code_consistency(self):
        """Test that error codes are consistent across different scenarios."""
        error_scenarios = [
            {"found_type": "dict"},
            {"found_type": "str"},
            {"found_type": "int"},
            {"found_type": "NoneType"}
        ]

        for scenario in error_scenarios:
            error = CorrectionsFileFormatError(
                result_id="consistency-test",
                file_path="/test/path",
                **scenario
            )

            response_body = error.to_http_response_body()

            # Error code should always be the same
            assert response_body["error"] == "CORRECTIONS_FILE_WRONG_TYPE"

            # Expected should always be array
            assert response_body["expected"] == "array"

            # Found should match the scenario
            assert response_body["found"] == scenario["found_type"]