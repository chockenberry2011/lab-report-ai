#!/usr/bin/env python3
"""
Test script to verify the corrections fix for lab_panels paths.
"""
import json
import sys
import os
from pathlib import Path

# Add the API path so we can import the modules
sys.path.append('./services/api')

try:
    from api.services.results_io import _apply_correction, normalize_result_id
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running from the lab-ai root directory")
    sys.exit(1)

def test_correction_fix():
    """Test that our fixes correctly handle path-based lab_panels corrections."""

    rid = "90fa7191-2f7f-46db-af78-c68658b7177e"

    # Test cases based on the actual corrections.json content
    test_cases = [
        {
            "name": "Field-based vendor_name (should work)",
            "correction": {
                "field": "vendor_name",
                "op": "replace",
                "value": "Test Vendor",
                "source": "test"
            },
            "should_apply": True
        },
        {
            "name": "Path-based vendor correction (should work)",
            "correction": {
                "path": "vendor.account_number",
                "op": "replace",
                "value": "ACC123",
                "source": "test"
            },
            "should_apply": True
        },
        {
            "name": "Field-based test_name without path (should NOT work)",
            "correction": {
                "field": "test_name",
                "op": "replace",
                "value": "Glucose Test Fixed",
                "source": "test"
            },
            "should_apply": False
        },
        {
            "name": "Path-based lab_panels test_name (should work)",
            "correction": {
                "path": "lab_panels.0.test_rows.1.test_name",
                "op": "replace",
                "value": "Glucose Test Fixed",
                "source": "test"
            },
            "should_apply": True
        }
    ]

    print("Testing corrections fix...")
    print("=" * 50)

    all_passed = True

    for test_case in test_cases:
        name = test_case["name"]
        correction = test_case["correction"]
        should_apply = test_case["should_apply"]

        print(f"\nTest: {name}")
        print(f"Correction: {correction}")

        try:
            result = _apply_correction(rid, correction)
            applied = result > 0

            if applied == should_apply:
                status = "✅ PASS"
            else:
                status = "❌ FAIL"
                all_passed = False

            print(f"Expected to apply: {should_apply}")
            print(f"Actually applied: {applied}")
            print(f"Result: {status}")

        except Exception as e:
            print(f"❌ ERROR: {e}")
            all_passed = False

    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All tests PASSED! The fix is working correctly.")
    else:
        print("💥 Some tests FAILED. Need to investigate.")

    return all_passed

if __name__ == "__main__":
    test_correction_fix()