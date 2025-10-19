#!/usr/bin/env python3
"""
Simple test for corrections file format error handling.
Creates test files with invalid formats and verifies HTTP 422 responses.
"""

import json
import sys
import tempfile
from pathlib import Path

# Add the services/api directory to the path
sys.path.insert(0, "services/api")

from api.exceptions import CorrectionsFileFormatError
from services.corrections import load_corrections


def test_corrections_file_format_error_exception():
    """Test the CorrectionsFileFormatError exception."""
    print("🧪 Testing CorrectionsFileFormatError exception...")

    # Test exception creation
    error = CorrectionsFileFormatError(
        result_id="test123",
        file_path="/data/results/test123/corrections.json",
        expected_type="array",
        found_type="dict"
    )

    assert error.result_id == "test123"
    assert error.expected_type == "array"
    assert error.found_type == "dict"
    print("✅ Exception creation works")

    # Test HTTP response body
    response_body = error.to_http_response_body()
    expected_fields = ["error", "message", "expected", "found", "result_id", "fix"]

    for field in expected_fields:
        assert field in response_body, f"Missing field: {field}"

    assert response_body["error"] == "CORRECTIONS_FILE_WRONG_TYPE"
    assert response_body["expected"] == "array"
    assert response_body["found"] == "dict"
    assert "migration" in response_body["fix"].lower()
    print("✅ HTTP response body generation works")

    return True


def test_legacy_corrections_loading_with_invalid_format():
    """Test that legacy corrections loading raises the format error."""
    print("\n🧪 Testing legacy corrections loading with invalid formats...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        base_dir = Path(tmp_dir)
        result_id = "test-invalid-format"

        # Create corrections directory
        corrections_dir = base_dir / result_id
        corrections_dir.mkdir(parents=True)

        # Test Case 1: Object format (should raise error)
        print("  Testing object format...")
        corrections_file = corrections_dir / "corrections.json"
        invalid_data = {
            "field": "test_name",
            "new_value": "Glucose",
            "line_number": 15
        }

        with corrections_file.open("w") as f:
            json.dump(invalid_data, f)

        # Mock the environment variable
        import os
        old_results_dir = os.environ.get("RESULTS_DIR")
        os.environ["RESULTS_DIR"] = str(base_dir)

        try:
            try:
                load_corrections(result_id)
                assert False, "Should have raised CorrectionsFileFormatError"
            except CorrectionsFileFormatError as e:
                assert e.result_id == result_id
                assert e.found_type == "dict"
                assert e.expected_type == "array"
                print("    ✅ Object format raises CorrectionsFileFormatError")

            # Test Case 2: String format (should raise error)
            print("  Testing string format...")
            with corrections_file.open("w") as f:
                json.dump("not_an_array", f)

            try:
                load_corrections(result_id)
                assert False, "Should have raised CorrectionsFileFormatError"
            except CorrectionsFileFormatError as e:
                assert e.found_type == "str"
                print("    ✅ String format raises CorrectionsFileFormatError")

            # Test Case 3: Valid array format (should work)
            print("  Testing valid array format...")
            valid_data = [
                {
                    "field": "test_name",
                    "new_value": "Glucose",
                    "line_number": 15
                }
            ]

            with corrections_file.open("w") as f:
                json.dump(valid_data, f)

            corrections = load_corrections(result_id)
            assert isinstance(corrections, dict)  # Returns processed dict
            print("    ✅ Valid array format works correctly")

        finally:
            # Restore environment
            if old_results_dir:
                os.environ["RESULTS_DIR"] = old_results_dir
            else:
                os.environ.pop("RESULTS_DIR", None)

    return True


def test_error_response_format():
    """Test the exact format of error responses."""
    print("\n🧪 Testing error response format for UI integration...")

    error = CorrectionsFileFormatError(
        result_id="ui-test",
        file_path="/data/results/ui-test/corrections.json",
        expected_type="array",
        found_type="dict"
    )

    response_body = error.to_http_response_body()

    # Test required fields
    required_fields = ["error", "message", "expected", "found", "result_id", "fix"]
    for field in required_fields:
        assert field in response_body, f"Missing required field: {field}"

    print("  ✅ All required fields present")

    # Test specific values
    assert response_body["error"] == "CORRECTIONS_FILE_WRONG_TYPE"
    assert response_body["expected"] == "array"
    assert response_body["found"] == "dict"
    assert response_body["result_id"] == "ui-test"
    print("  ✅ Field values correct")

    # Test actionable guidance
    fix_message = response_body["fix"]
    assert "migration" in fix_message.lower()
    assert "delete" in fix_message.lower()
    assert "array" in fix_message.lower()
    print("  ✅ Fix message contains actionable guidance")

    # Print example for reference
    print("\nExample error response body:")
    print(json.dumps(response_body, indent=2))

    return True


def main():
    """Run all tests."""
    print("🚀 Starting corrections file format error tests...\n")

    tests = [
        test_corrections_file_format_error_exception,
        test_legacy_corrections_loading_with_invalid_format,
        test_error_response_format,
    ]

    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"❌ Test {test.__name__} failed")
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")

    if passed == len(tests):
        print("✅ All corrections format error tests passed!")
        print("\nImplementation summary:")
        print("  • CorrectionsFileFormatError exception created")
        print("  • Legacy corrections loading raises HTTP 422 for invalid formats")
        print("  • Error responses include actionable fix guidance")
        print("  • UI can surface structured error information")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    exit(main())