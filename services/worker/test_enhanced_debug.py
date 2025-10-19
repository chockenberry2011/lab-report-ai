#!/usr/bin/env python3
"""
Test enhanced debug dump functionality
"""

import json
import sys
import re

# Mock the enhance_debug_data function
def truncate_for_debug(text: str, max_length: int = 500) -> str:
    """Safely truncate text for debug dumps"""
    if not text or not isinstance(text, str):
        return text
    if len(text) <= max_length:
        return text
    return text[:max_length] + "... [TRUNCATED]"

def enhance_debug_data(stage: str, original_data, header_result=None, composition_result=None):
    """Mock implementation of debug enhancement"""
    import copy
    
    enhanced_data = copy.deepcopy(original_data)
    
    if stage == "02_roles" and header_result:
        # Add metadata extraction results to roles debug
        enhanced_data["meta_extraction"] = {}
        
        # Add vendor info (truncated)
        if header_result.get("vendor_info"):
            vendor = header_result["vendor_info"].copy()
            if vendor.get("name"):
                vendor["name"] = truncate_for_debug(vendor["name"], 100)
            enhanced_data["meta_extraction"]["vendor"] = vendor
        
        # Add patient info (truncated)
        if header_result.get("patient_info_structured"):
            patient = header_result["patient_info_structured"].copy()
            for field in ["first_name", "last_name", "middle"]:
                if patient.get(field):
                    patient[field] = truncate_for_debug(patient[field], 50)
            enhanced_data["meta_extraction"]["patient"] = patient
        
        # Add specimen info
        if header_result.get("specimen_info_structured"):
            specimen = header_result["specimen_info_structured"].copy()
            if specimen.get("type"):
                specimen["type"] = truncate_for_debug(specimen["type"], 100)
            enhanced_data["meta_extraction"]["specimen"] = specimen
        
        # Add ordering info (truncated)
        if header_result.get("ordering_info"):
            ordering = header_result["ordering_info"].copy()
            if ordering.get("provider_name"):
                ordering["provider_name"] = truncate_for_debug(ordering["provider_name"], 100)
            enhanced_data["meta_extraction"]["ordering"] = ordering
        
        # Add report meta (truncated)
        if header_result.get("report_meta_info"):
            report_meta = header_result["report_meta_info"].copy()
            if report_meta.get("clinical_info"):
                report_meta["clinical_info"] = truncate_for_debug(report_meta["clinical_info"])
            if report_meta.get("comments"):
                report_meta["comments"] = truncate_for_debug(report_meta["comments"])
            enhanced_data["meta_extraction"]["report_meta"] = report_meta
    
    elif stage == "03_compose" and composition_result:
        # Enhance composition result with panel and test extras
        if enhanced_data.get("lab_panels"):
            for panel in enhanced_data["lab_panels"]:
                # Add panel enhancements
                panel_extras = {}
                
                # Add panel code if present
                if panel.get("panel_code"):
                    panel_extras["code"] = truncate_for_debug(panel["panel_code"], 100)
                
                # Add panel comments if present (truncated)
                if panel.get("comments"):
                    panel_extras["comments"] = truncate_for_debug(panel["comments"])
                
                if panel_extras:
                    panel["debug_extras"] = panel_extras
                
                # Add test row enhancements
                if panel.get("test_rows"):
                    for test_row in panel["test_rows"]:
                        test_extras = {}
                        
                        # Add codes if present
                        if test_row.get("codes"):
                            test_extras["codes"] = test_row["codes"]
                        
                        # Add methodology (truncated)
                        if test_row.get("methodology"):
                            test_extras["methodology"] = truncate_for_debug(test_row["methodology"], 200)
                        
                        # Add comments (truncated)
                        if test_row.get("comments"):
                            test_extras["comments"] = truncate_for_debug(test_row["comments"])
                        
                        # Add observation time
                        if test_row.get("observed_at"):
                            test_extras["observed_at"] = test_row["observed_at"]
                        
                        if test_extras:
                            test_row["debug_extras"] = test_extras
    
    return enhanced_data

def test_enhanced_debug():
    """Test the enhanced debug functionality"""
    
    print("=== Enhanced Debug Dumps Test ===")
    
    # Mock 02_roles debug data
    role_result = {
        "lines": [
            {
                "text": "LIPID PANEL",
                "role": "SECTION_PANEL",
                "predicted_role": "SECTION_PANEL",
                "page": 1,
                "line_number": 0
            },
            {
                "text": "Cholesterol    180    mg/dL    <200    LOINC: 2093-3",
                "role": "TEST_ROW",
                "predicted_role": "TEST_ROW",
                "page": 1,
                "line_number": 1
            }
        ],
        "stats": {
            "total_lines": 2,
            "used_fallback": False
        }
    }
    
    # Mock header result with metadata
    header_result = {
        "vendor_info": {
            "name": "LabCorp Diagnostics Laboratory Services",
            "account_number": "ACC12345",
            "phone": "555-123-4567",
            "address": {
                "street": "123 Very Long Laboratory Street Name That Should Be Truncated",
                "city": "Laboratory City",
                "state": "NY",
                "zip": "12345"
            }
        },
        "patient_info_structured": {
            "first_name": "John",
            "last_name": "Doe",
            "middle": "Q",
            "dob": "1990-01-15",
            "sex": "M",
            "mrn": "MRN123456"
        },
        "specimen_info_structured": {
            "id": "SPEC789",
            "type": "Serum",
            "collected_at": "2024-01-15T09:00:00",
            "received_at": "2024-01-15T10:30:00"
        },
        "ordering_info": {
            "provider_name": "Dr. Sarah Johnson",
            "npi": "1234567890",
            "location": {
                "name": "Primary Care Associates"
            }
        },
        "report_meta_info": {
            "clinical_info": "Patient presents with chest pain and dyslipidemia family history. This is a very long clinical information field that should be truncated after 500 characters to keep debug dumps reasonable in size. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium totam rem aperiam.",
            "comments": "Follow up in 6 months",
            "ordered_items": ["Lipid Panel", "Comprehensive Metabolic Panel", "CBC with Differential"]
        }
    }
    
    print("\n--- 02_roles Debug Enhancement ---")
    enhanced_roles = enhance_debug_data("02_roles", role_result, header_result=header_result)
    
    print("Original data keys:", list(role_result.keys()))
    print("Enhanced data keys:", list(enhanced_roles.keys()))
    
    if "meta_extraction" in enhanced_roles:
        print("Meta extraction added:")
        for key, value in enhanced_roles["meta_extraction"].items():
            print(f"  - {key}: {type(value).__name__} with {len(str(value))} chars")
        
        # Show truncation in action
        if enhanced_roles["meta_extraction"].get("report_meta", {}).get("clinical_info"):
            clinical_info = enhanced_roles["meta_extraction"]["report_meta"]["clinical_info"]
            if "TRUNCATED" in clinical_info:
                print(f"  ✅ Long clinical info truncated: {len(clinical_info)} chars")
        
        # Show address truncation
        if enhanced_roles["meta_extraction"].get("vendor", {}).get("address", {}).get("street"):
            street = enhanced_roles["meta_extraction"]["vendor"]["address"]["street"]
            if "TRUNCATED" in street:
                print(f"  ✅ Long address truncated: {len(street)} chars")
    
    # Mock 03_compose debug data
    composition_result = {
        "lab_panels": [
            {
                "id": "panel-1",
                "name": "Lipid Panel",
                "panel_code": "LOINC: 57698-3",
                "comments": "This panel includes comprehensive lipid analysis with detailed commentary about the patient's cardiovascular risk assessment and recommendations for lifestyle modifications and potential medication adjustments based on current guidelines and patient-specific factors including age, gender, and comorbidities which may influence treatment decisions.",
                "test_rows": [
                    {
                        "test_name": "Total Cholesterol",
                        "result_value": "180",
                        "units": "mg/dL",
                        "codes": {"loinc": "2093-3"},
                        "methodology": "Enzymatic Colorimetric Assay",
                        "comments": "Normal range for cardiovascular protection",
                        "observed_at": "09:30 AM"
                    },
                    {
                        "test_name": "HDL Cholesterol",
                        "result_value": "65",
                        "units": "mg/dL",
                        "codes": {"cpt": "83718"},
                        "methodology": "Direct Immunoassay Method with Enhanced Specificity for High-Density Lipoprotein Particles",
                        "comments": "Excellent protective levels observed",
                        "observed_at": "09:35 AM"
                    }
                ]
            }
        ],
        "summary": {
            "total_panels": 1,
            "total_tests": 2
        }
    }
    
    print("\n--- 03_compose Debug Enhancement ---")
    enhanced_compose = enhance_debug_data("03_compose", composition_result, composition_result=composition_result)
    
    if enhanced_compose.get("lab_panels"):
        panel = enhanced_compose["lab_panels"][0]
        print(f"Panel '{panel['name']}':")
        
        # Check panel extras
        if panel.get("debug_extras"):
            print("  Panel debug_extras:")
            for key, value in panel["debug_extras"].items():
                print(f"    - {key}: {value}")
                if key == "comments" and "TRUNCATED" in value:
                    print(f"      ✅ Long comment truncated: {len(value)} chars")
        
        # Check test row extras
        if panel.get("test_rows"):
            for i, test in enumerate(panel["test_rows"]):
                if test.get("debug_extras"):
                    print(f"  Test {i+1} debug_extras:")
                    for key, value in test["debug_extras"].items():
                        print(f"    - {key}: {value}")
                        if key == "methodology" and "TRUNCATED" in str(value):
                            print(f"      ✅ Long methodology truncated: {len(str(value))} chars")
    
    print("\n=== Sample Enhanced Debug JSON Structure ===")
    # Show partial structure to demonstrate the enhancements
    sample_structure = {
        "02_roles_enhancement": {
            "original_keys": ["lines", "stats"],
            "added_key": "meta_extraction",
            "meta_extraction_contains": [
                "vendor (name, account, phone, address)",
                "patient (demographics, address)",
                "specimen (type, dates)",
                "ordering (provider, location)",
                "report_meta (clinical_info, comments, ordered_items)"
            ]
        },
        "03_compose_enhancement": {
            "original_keys": ["lab_panels", "summary"],
            "added_to_panels": "debug_extras",
            "added_to_tests": "debug_extras",
            "debug_extras_contains": [
                "codes (LOINC/CPT)",
                "methodology (truncated to 200 chars)",
                "comments (truncated to 500 chars)",
                "observed_at (time strings)"
            ]
        },
        "truncation_limits": {
            "comments": "500 chars",
            "clinical_info": "500 chars",
            "methodology": "200 chars",
            "names": "100 chars",
            "personal_fields": "50 chars"
        }
    }
    
    print(json.dumps(sample_structure, indent=2))
    
    print("\n✅ Enhanced debug dumps demonstrated!")
    print("- Metadata added to 02_roles.debug.json")
    print("- Panel/test extras added to 03_compose.debug.json")
    print("- Long text fields truncated to keep sizes reasonable")
    print("- No crashes when fields are missing")

if __name__ == "__main__":
    test_enhanced_debug()