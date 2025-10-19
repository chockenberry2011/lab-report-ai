#!/usr/bin/env python3
"""
Simple test for the corrections append functionality.
Tests the exact requirements specified.
"""

import json
import requests
import os


def test_single_object_append():
    """Test appending a single correction object."""
    API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
    result_id = "test-single-object"

    print("Testing single object append...")

    # Single correction object
    payload = {
        "field": "test_name",
        "new_value": "Glucose",
        "old_value": "GLU",
        "line_number": 15
    }

    response = requests.post(
        f"{API_BASE}/results/{result_id}/corrections",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        if "corrections" in data and len(data["corrections"]) >= 1:
            print("✅ Single object append works")
            return True

    print("❌ Single object append failed")
    return False


def test_array_append():
    """Test appending an array of corrections."""
    API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
    result_id = "test-array-append"

    print("\nTesting array append...")

    # Array of corrections
    payload = [
        {"field": "test_name", "new_value": "Glucose", "line_number": 15},
        {"field": "result_value", "new_value": "72", "line_number": 15}
    ]

    response = requests.post(
        f"{API_BASE}/results/{result_id}/corrections",
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200:
        data = response.json()
        if "corrections" in data and len(data["corrections"]) >= 2:
            print("✅ Array append works")
            return True

    print("❌ Array append failed")
    return False


def test_current_endpoint():
    """Test what the current endpoint actually returns."""
    API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
    result_id = "test-current-endpoint"

    print("\nTesting current endpoint behavior...")

    # Test with the old format first
    old_format = {
        "corrections": [
            {"field": "test_name", "new_value": "Glucose", "line_number": 15}
        ]
    }

    response = requests.post(
        f"{API_BASE}/results/{result_id}/corrections",
        json=old_format,
        headers={"Content-Type": "application/json"}
    )

    print(f"Old format - Status: {response.status_code}")
    print(f"Old format - Response: {response.text}")

    # Test with single object
    single_object = {"field": "test_name", "new_value": "Glucose", "line_number": 15}

    response = requests.post(
        f"{API_BASE}/results/{result_id}/corrections",
        json=single_object,
        headers={"Content-Type": "application/json"}
    )

    print(f"Single object - Status: {response.status_code}")
    print(f"Single object - Response: {response.text}")

    return True


def main():
    print("🧪 Testing corrections append functionality...\n")

    test_current_endpoint()
    test_single_object_append()
    test_array_append()

    print("\n✅ Test completed")


if __name__ == "__main__":
    main()