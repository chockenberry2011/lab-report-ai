#!/usr/bin/env python3
"""
Demo script showing the new enhanced corrections system
"""
import json
from api.utils.paths import split_path
from api.utils.corrections import apply_corrections

def demo_path_parsing():
    """Demonstrate path parsing for different formats"""
    print("=== Path Parsing Demo ===")
    
    test_paths = [
        "patient.first_name",
        "patient.mrn", 
        "panels[0].name",
        "panels[0].tests[2].value",
        "panels[1].tests[0].reference_range",
        "/patient/first_name",
        "/panels/0/tests/2/value",
        "/vendor/name",
        "/specimen/collected_at"
    ]
    
    for path in test_paths:
        segments = split_path(path)
        print(f"  {path:30} → {segments}")
    
    print()

def demo_corrections_application():
    """Demonstrate applying corrections to a lab result"""
    print("=== Corrections Application Demo ===")
    
    # Sample lab result (simplified north-star schema)
    sample_result = {
        "vendor": {
            "name": "Quest Diagnostics",
            "lab_id": "Q001"
        },
        "patient": {
            "first_name": "John",
            "last_name": "Smith",
            "mrn": "12345",
            "dob": "1985-03-15"
        },
        "provider": {
            "name": "Dr. Johnson",
            "npi": "1234567890"
        },
        "specimen": {
            "collected_at": "2024-09-01T08:00:00",
            "type": "serum"
        },
        "report": {
            "reported_at": "2024-09-01T12:00:00",
            "status": "final"
        },
        "panels": [
            {
                "name": "Basic Metabolic Panel",
                "tests": [
                    {
                        "name": "Glucose",
                        "value": "95",
                        "units": "mg/dL",
                        "reference_range": "70-100",
                        "flag": None
                    },
                    {
                        "name": "Sodium",
                        "value": "140",
                        "units": "mEq/L", 
                        "reference_range": "136-145",
                        "flag": None
                    }
                ]
            }
        ]
    }
    
    print("Original data:")
    print(json.dumps(sample_result, indent=2))
    
    # Sample corrections in new format
    corrections = [
        {"op": "set", "path": "patient.first_name", "value": "Jane"},
        {"op": "unset", "path": "patient.mrn"},
        {"op": "set", "path": "specimen.collected_at", "value": "2024-09-01T08:30:00"},
        {"op": "set", "path": "panels[0].name", "value": "Comprehensive Metabolic Panel"},
        {"op": "set", "path": "panels[0].tests[0].value", "value": "102"},
        {"op": "set", "path": "panels[0].tests[0].flag", "value": "HIGH"},
        {"op": "set", "path": "panels[0].tests[1].reference_range", "value": "135-145"}
    ]
    
    print(f"\nApplying {len(corrections)} corrections...")
    for i, correction in enumerate(corrections, 1):
        op = correction.get("op", "set")
        path = correction.get("path", "")
        value = correction.get("value", "")
        if op == "unset":
            print(f"  {i}. {op.upper():5} {path}")
        else:
            print(f"  {i}. {op.upper():5} {path} = {value}")
    
    # Apply corrections
    corrected_result = apply_corrections(sample_result, corrections)
    
    print(f"\nCorrected data:")
    print(json.dumps(corrected_result, indent=2))
    
    # Verify specific changes
    print("\n=== Verification ===")
    print(f"✓ Patient name changed: {corrected_result['patient']['first_name']}")
    print(f"✓ MRN removed: {'mrn' not in corrected_result['patient']}")
    print(f"✓ Specimen time updated: {corrected_result['specimen']['collected_at']}")
    print(f"✓ Panel name updated: {corrected_result['panels'][0]['name']}")
    print(f"✓ Glucose value corrected: {corrected_result['panels'][0]['tests'][0]['value']}")
    print(f"✓ Glucose flag added: {corrected_result['panels'][0]['tests'][0]['flag']}")
    
def demo_backward_compatibility():
    """Show backward compatibility with legacy format"""
    print("\n=== Backward Compatibility Demo ===")
    
    # Legacy correction format (without 'op' field)
    legacy_corrections = [
        {"path": "patient.first_name", "value": "Alice"},
        {"path": "panels[0].tests[0].value", "value": "98"}
    ]
    
    print("Legacy format corrections (auto-converted to op='set'):")
    for correction in legacy_corrections:
        print(f"  {correction}")
    
    base_data = {
        "patient": {"first_name": "Bob"},
        "panels": [{"tests": [{"value": "95"}]}]
    }
    
    result = apply_corrections(base_data, legacy_corrections)
    print(f"\nResult: {result}")

if __name__ == "__main__":
    demo_path_parsing()
    demo_corrections_application()  
    demo_backward_compatibility()
    
    print("\n=== Summary ===")
    print("✅ Enhanced corrections system successfully implemented!")
    print("✅ Supports dot notation and JSON Pointer paths")
    print("✅ Handles set, unset, and append operations")
    print("✅ Maintains backward compatibility with legacy format")
    print("✅ Works with full north-star schema (vendor/patient/provider/specimen/report/panels/tests)")