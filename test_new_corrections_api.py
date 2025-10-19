#!/usr/bin/env python3
"""
Test script for the new corrections API endpoints
Run this after starting the FastAPI service to verify functionality
"""

import requests
import json
import sys

API_BASE = "http://localhost:8000"  # Adjust as needed

def test_corrections_api():
    print("Testing New Corrections API")
    print("=" * 50)

    # Test case 1: POST with envelope format
    print("\n1. Testing POST with envelope format...")
    envelope_payload = {
        "corrections": [
            {
                "field": "patient.first_name",
                "old_value": "John",
                "new_value": "Jane",
                "source": "test-script"
            }
        ]
    }

    try:
        response = requests.post(
            f"{API_BASE}/results/test-uuid.03_compose.debug/corrections",
            json=envelope_payload,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Success: {result}")
            if result.get("ok") and result.get("saved_count") == 1:
                print("   ✓ Response format correct")
            else:
                print("   ✗ Unexpected response format")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test case 2: POST with array format
    print("\n2. Testing POST with array format...")
    array_payload = [
        {
            "field": "patient.last_name",
            "old_value": "Smith",
            "new_value": "Johnson",
            "source": "test-script"
        }
    ]

    try:
        response = requests.post(
            f"{API_BASE}/results/test-uuid.03_compose.debug/corrections",
            json=array_payload,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Success: {result}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test case 3: GET corrections
    print("\n3. Testing GET corrections...")
    try:
        response = requests.get(
            f"{API_BASE}/results/test-uuid.03_compose.debug/corrections"
        )

        if response.status_code == 200:
            result = response.json()
            print(f"   ✓ Success: {json.dumps(result, indent=2)}")

            # Check Cache-Control header
            if response.headers.get("Cache-Control") == "no-store":
                print("   ✓ Cache-Control header correct")
            else:
                print(f"   ✗ Cache-Control header: {response.headers.get('Cache-Control')}")

            # Check format
            if "corrections" in result and isinstance(result["corrections"], list):
                print("   ✓ Response format correct")
                print(f"   ✓ Found {len(result['corrections'])} corrections")
            else:
                print("   ✗ Unexpected response format")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test case 4: GET non-existent corrections
    print("\n4. Testing GET non-existent corrections...")
    try:
        response = requests.get(
            f"{API_BASE}/results/non-existent-uuid/corrections"
        )

        if response.status_code == 200:
            result = response.json()
            if result == {"corrections": []}:
                print("   ✓ Empty corrections returned correctly")
            else:
                print(f"   ✗ Unexpected response: {result}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test case 5: POST invalid format
    print("\n5. Testing POST with invalid format...")
    invalid_payload = {"invalid": "format"}

    try:
        response = requests.post(
            f"{API_BASE}/results/test-uuid/corrections",
            json=invalid_payload,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 400:
            result = response.json()
            if "Unknown corrections format" in result.get("detail", ""):
                print("   ✓ Invalid format correctly rejected")
            else:
                print(f"   ✗ Unexpected error: {result}")
        else:
            print(f"   ✗ Expected 400, got: {response.status_code}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    # Test case 6: Health details endpoint
    print("\n6. Testing health details...")
    try:
        response = requests.get(f"{API_BASE}/healthz/details")

        if response.status_code == 200:
            result = response.json()
            if result.get("ok") and "data_root" in result:
                print(f"   ✓ Health details: {result}")
            else:
                print(f"   ✗ Unexpected response: {result}")
        else:
            print(f"   ✗ Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"   ✗ Error: {e}")

    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nTo run this test:")
    print("1. Start the FastAPI service")
    print("2. Run: python3 test_new_corrections_api.py")
    print("3. Check that all tests show ✓")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        API_BASE = sys.argv[1]
        print(f"Using API base: {API_BASE}")

    test_corrections_api()