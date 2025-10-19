"""
Test script for the panel composer
"""

import json
from .composer import PanelComposer


def create_test_data():
    """Create sample test data for testing the composer"""
    return [
        # Page 1 - Header and first panel
        {"text": "PAGE_HEADER Lab Results Report", "role": "PAGE_HEADER", "page": 1, "yNorm": 0.9, "xLeft": 0, "xRight": 100},
        {"text": "CHEMISTRY PANEL", "role": "SECTION_PANEL", "page": 1, "yNorm": 0.8, "xLeft": 0, "xRight": 100, "fontSize": 14, "isBold": True},
        {"text": "Glucose 95 mg/dL 70-100", "role": "TEST_ROW", "page": 1, "yNorm": 0.7, "xLeft": 10, "xRight": 90},
        {"text": "Sodium 140 mEq/L 136-145", "role": "TEST_ROW", "page": 1, "yNorm": 0.6, "xLeft": 10, "xRight": 90},
        {"text": "Potassium 4.2 mEq/L 3.5-5.1", "role": "TEST_ROW", "page": 1, "yNorm": 0.5, "xLeft": 10, "xRight": 90},
        {"text": "PAGE_FOOTER Page 1", "role": "PAGE_FOOTER", "page": 1, "yNorm": 0.1, "xLeft": 0, "xRight": 100},
        
        # Page 2 - Continued panel
        {"text": "PAGE_HEADER Lab Results Report", "role": "PAGE_HEADER", "page": 2, "yNorm": 0.9, "xLeft": 0, "xRight": 100},
        {"text": "Chloride 101 mEq/L 98-107", "role": "TEST_ROW", "page": 2, "yNorm": 0.8, "xLeft": 10, "xRight": 90},
        {"text": "BUN 18 mg/dL 7-20", "role": "TEST_ROW", "page": 2, "yNorm": 0.7, "xLeft": 10, "xRight": 90},
        
        # New panel on same page
        {"text": "LIPID PANEL", "role": "SECTION_PANEL", "page": 2, "yNorm": 0.6, "xLeft": 0, "xRight": 100, "fontSize": 14, "isBold": True},
        {"text": "Total Cholesterol 185 mg/dL <200", "role": "TEST_ROW", "page": 2, "yNorm": 0.5, "xLeft": 10, "xRight": 90},
        {"text": "HDL Cholesterol 55 mg/dL >40", "role": "TEST_ROW", "page": 2, "yNorm": 0.4, "xLeft": 10, "xRight": 90},
        {"text": "LDL Cholesterol 110 mg/dL <100 HIGH", "role": "TEST_ROW", "page": 2, "yNorm": 0.3, "xLeft": 10, "xRight": 90},
        {"text": "PAGE_FOOTER Page 2", "role": "PAGE_FOOTER", "page": 2, "yNorm": 0.1, "xLeft": 0, "xRight": 100},
        
        # Page 3 - Another panel
        {"text": "PAGE_HEADER Lab Results Report", "role": "PAGE_HEADER", "page": 3, "yNorm": 0.9, "xLeft": 0, "xRight": 100},
        {"text": "CBC WITH DIFFERENTIAL", "role": "SECTION_PANEL", "page": 3, "yNorm": 0.8, "xLeft": 0, "xRight": 100, "fontSize": 14, "isBold": True},
        {"text": "WBC 7.2 K/uL 4.5-11.0", "role": "TEST_ROW", "page": 3, "yNorm": 0.7, "xLeft": 10, "xRight": 90},
        {"text": "RBC 4.8 M/uL 4.7-6.1", "role": "TEST_ROW", "page": 3, "yNorm": 0.6, "xLeft": 10, "xRight": 90},
        {"text": "Hemoglobin 14.2 g/dL 14.0-18.0", "role": "TEST_ROW", "page": 3, "yNorm": 0.5, "xLeft": 10, "xRight": 90},
        {"text": "PAGE_FOOTER Page 3", "role": "PAGE_FOOTER", "page": 3, "yNorm": 0.1, "xLeft": 0, "xRight": 100},
    ]


def test_basic_composition():
    """Test basic panel composition"""
    print("Testing basic panel composition...")
    
    # Create test data
    test_data = create_test_data()
    
    # Initialize composer
    composer = PanelComposer()
    
    # Compose panels
    result = composer.compose(test_data)
    
    # Verify results
    print(f"Found {len(result.panels)} panels")
    print(f"Total test rows: {result.total_test_rows}")
    print(f"Page breaks handled: {result.page_breaks_handled}")
    
    # Print panel details
    for i, panel in enumerate(result.panels, 1):
        print(f"\nPanel {i}: {panel.name}")
        print(f"  Started at page {panel.started_at_page}, line {panel.started_at_line}")
        print(f"  Test rows: {len(panel.test_rows)}")
        print(f"  Continuity score: {panel.continuity_score:.2f}")
        print(f"  Coherence score: {panel.calculate_coherence_score():.2f}")
        
        for j, test_row in enumerate(panel.test_rows, 1):
            print(f"    {j}. {test_row.test_name or 'Unknown'}: {test_row.result_value or 'N/A'} {test_row.units or ''}")
    
    return result


def test_ehr_output():
    """Test EHR JSON output"""
    print("\n" + "="*50)
    print("Testing EHR JSON output...")
    
    test_data = create_test_data()
    composer = PanelComposer()
    result = composer.compose(test_data)
    
    # Generate EHR JSON
    ehr_json = result.to_ehr_json()
    print("EHR JSON generated successfully")
    
    # Parse and verify
    ehr_data = json.loads(ehr_json)
    print(f"Document info: {ehr_data['document_info']['total_panels']} panels, {ehr_data['document_info']['total_tests']} tests")
    
    # Save to file for inspection
    with open('/tmp/test_composer_output.json', 'w') as f:
        f.write(ehr_json)
    print("Sample output saved to /tmp/test_composer_output.json")
    
    return ehr_data


if __name__ == '__main__':
    print("Panel Composer Test")
    print("=" * 50)
    
    # Run basic test
    result = test_basic_composition()
    
    # Test EHR output
    ehr_data = test_ehr_output()
    
    print("\n" + "="*50)
    print("All tests completed successfully!")
    print(f"Processing time: {result.processing_time:.3f}s")
    print(f"Efficiency: {result.get_summary()['efficiency_score']:.1f} tests/second")