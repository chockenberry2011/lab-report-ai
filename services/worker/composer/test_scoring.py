"""
Test script for the scoring module
"""

import json
from .composer import PanelComposer
from .scoring import LabDataScorer


def create_test_data_with_issues():
    """Create test data with various quality issues to test scoring"""
    return [
        # Page 1 - Good quality chemistry panel
        {"text": "PAGE_HEADER Lab Results Report", "role": "PAGE_HEADER", "page": 1, "yNorm": 0.9},
        {"text": "CHEMISTRY PANEL", "role": "SECTION_PANEL", "page": 1, "yNorm": 0.8, "fontSize": 14, "isBold": True},
        {"text": "Glucose 95 mg/dL 70-100", "role": "TEST_ROW", "page": 1, "yNorm": 0.7},
        {"text": "Sodium 140 mEq/L 136-145", "role": "TEST_ROW", "page": 1, "yNorm": 0.6},
        {"text": "Potassium 4.2 mEq/L 3.5-5.1", "role": "TEST_ROW", "page": 1, "yNorm": 0.5},
        
        # Page 2 - Panel with quality issues
        {"text": "PAGE_HEADER Lab Results Report", "role": "PAGE_HEADER", "page": 2, "yNorm": 0.9},
        {"text": "PROBLEMATIC TESTS", "role": "SECTION_PANEL", "page": 2, "yNorm": 0.8, "fontSize": 14, "isBold": True},
        {"text": "Test1 RESULT xyz/invalid", "role": "TEST_ROW", "page": 2, "yNorm": 0.7},  # Bad units, unparseable value
        {"text": "??? HIGH", "role": "TEST_ROW", "page": 2, "yNorm": 0.6},  # Bad test name, no value
        {"text": "Hemoglobin unclear range", "role": "TEST_ROW", "page": 2, "yNorm": 0.5},  # No value, bad range
        
        # Page 3 - Mixed quality panel
        {"text": "PAGE_HEADER Lab Results Report", "role": "PAGE_HEADER", "page": 3, "yNorm": 0.9},
        {"text": "MIXED QUALITY PANEL", "role": "SECTION_PANEL", "page": 3, "yNorm": 0.8, "fontSize": 14, "isBold": True},
        {"text": "WBC 7.2 K/uL 4.5-11.0", "role": "TEST_ROW", "page": 3, "yNorm": 0.7},  # Good
        {"text": "RBC 4.8 badunits >4.0", "role": "TEST_ROW", "page": 3, "yNorm": 0.6},  # Bad units
        {"text": "Platelets NORMAL", "role": "TEST_ROW", "page": 3, "yNorm": 0.5},  # Text result, no units
    ]


def test_field_scoring():
    """Test individual field scoring"""
    print("Testing individual field scoring...")
    
    scorer = LabDataScorer()
    
    # Test various value types
    test_cases = [
        # Good cases
        ("TestName", "95", "mg/dL", "70-100", "Should score high"),
        ("Glucose", "4.2", "mEq/L", "3.5-5.1", "Should score high"),
        ("WBC", "7200", "K/uL", "4500-11000", "Should score high"),
        
        # Poor cases  
        ("???", "RESULT", "xyz/invalid", "unclear", "Should score low"),
        ("", "", "", "", "Empty fields should score 0"),
        ("Test", "unparseable", "badunit", "malformed", "Bad parsing should score low"),
        
        # Mixed cases
        ("Hemoglobin", "14.2", "g/dL", "NORMAL", "Mixed quality"),
        ("TestName", "POSITIVE", "", ">reference", "Text result, no units"),
    ]
    
    print("\nField scoring results:")
    for test_name, value, units, ref_range, description in test_cases:
        from .schemas import TestRow
        
        test_row = TestRow(
            text=f"{test_name} {value} {units} {ref_range}",
            page=1,
            line_number=1,
            y_norm=0.5,
            test_name=test_name,
            result_value=value,
            units=units,
            reference_range=ref_range
        )
        
        confidence = scorer.score_test_row(test_row)
        
        print(f"  {description}:")
        print(f"    Overall: {confidence.overall:.2f}")
        print(f"    Value parse: {confidence.value_parse:.2f}")
        print(f"    Unit validity: {confidence.unit_validity:.2f}")
        print(f"    Ref range: {confidence.reference_range:.2f}")
        print(f"    Name clarity: {confidence.test_name_clarity:.2f}")


def test_comprehensive_scoring():
    """Test full composition with scoring"""
    print("\n" + "="*60)
    print("Testing comprehensive scoring with problematic data...")
    
    # Create test data with quality issues
    test_data = create_test_data_with_issues()
    
    # Mock classifier probabilities (some low confidence predictions)
    classifier_probabilities = {
        7: 0.6,   # Test1 line - low confidence in role classification
        8: 0.4,   # ??? line - very low confidence
        9: 0.7,   # Hemoglobin line - moderate confidence
        13: 0.9,  # WBC line - high confidence
        14: 0.8,  # RBC line - good confidence
        15: 0.75  # Platelets line - good confidence
    }
    
    # Initialize composer with scoring enabled
    composer = PanelComposer(enable_scoring=True)
    
    # Compose with scoring
    result = composer.compose(test_data, classifier_probabilities)
    
    # Print comprehensive results
    print(f"\nDocument-level scoring:")
    print(f"  Overall document score: {result.document_score:.3f}")
    print(f"  Needs review: {result.needs_review}")
    print(f"  Review reasons: {result.review_reasons}")
    
    if result.confidence_distribution:
        dist = result.confidence_distribution
        print(f"  Confidence distribution:")
        print(f"    Mean: {dist['mean']:.3f}")
        print(f"    Median: {dist['median']:.3f}")
        print(f"    Range: {dist['min']:.3f} - {dist['max']:.3f}")
        print(f"    Std Dev: {dist['std']:.3f}")
    
    print(f"\nPanel-level scoring:")
    for i, panel in enumerate(result.panels, 1):
        print(f"  Panel {i}: {panel.name}")
        print(f"    Panel score: {panel.panel_score:.3f}")
        print(f"    Needs review: {panel.needs_review}")
        print(f"    Review reasons: {panel.review_reasons}")
        print(f"    Test rows: {len(panel.test_rows)}")
        
        # Show individual test row confidences
        for j, test_row in enumerate(panel.test_rows, 1):
            print(f"      Test {j}: {test_row.test_name or 'Unknown'}")
            print(f"        Overall confidence: {test_row.confidence:.3f}")
            if test_row.field_confidences:
                fc = test_row.field_confidences
                print(f"        Field confidences: V={fc.get('value_parse', 0):.2f}, "
                      f"U={fc.get('unit_validity', 0):.2f}, "
                      f"R={fc.get('reference_range', 0):.2f}, "
                      f"N={fc.get('test_name_clarity', 0):.2f}")
    
    return result


def test_ehr_output_with_scoring():
    """Test EHR JSON output with full scoring information"""
    print("\n" + "="*60)
    print("Testing EHR output with scoring information...")
    
    test_data = create_test_data_with_issues()
    composer = PanelComposer(enable_scoring=True)
    result = composer.compose(test_data)
    
    # Generate EHR JSON with scoring
    ehr_json = result.to_ehr_json()
    ehr_data = json.loads(ehr_json)
    
    print("EHR JSON with scoring generated successfully")
    print(f"Document needs review: {ehr_data['document_info']['needs_review']}")
    print(f"Document score: {ehr_data['document_info']['document_score']:.3f}")
    
    # Count panels that need review
    panels_needing_review = sum(1 for panel in ehr_data['lab_panels'] if panel['needs_review'])
    print(f"Panels needing review: {panels_needing_review}/{len(ehr_data['lab_panels'])}")
    
    # Save to file for inspection
    with open('/tmp/test_scoring_output.json', 'w') as f:
        f.write(ehr_json)
    print("Sample output with scoring saved to /tmp/test_scoring_output.json")
    
    return ehr_data


def test_thresholds():
    """Test different scoring thresholds"""
    print("\n" + "="*60)
    print("Testing different scoring thresholds...")
    
    test_data = create_test_data_with_issues()
    
    # Test with strict thresholds
    strict_config = {
        'value_parse_threshold': 0.9,
        'unit_validity_threshold': 0.9,
        'ref_range_threshold': 0.8,
        'panel_score_threshold': 0.8,
        'document_score_threshold': 0.8
    }
    
    composer_strict = PanelComposer(enable_scoring=True, scoring_config=strict_config)
    result_strict = composer_strict.compose(test_data)
    
    # Test with lenient thresholds
    lenient_config = {
        'value_parse_threshold': 0.4,
        'unit_validity_threshold': 0.4,
        'ref_range_threshold': 0.3,
        'panel_score_threshold': 0.4,
        'document_score_threshold': 0.4
    }
    
    composer_lenient = PanelComposer(enable_scoring=True, scoring_config=lenient_config)
    result_lenient = composer_lenient.compose(test_data)
    
    print(f"Strict thresholds:")
    print(f"  Document score: {result_strict.document_score:.3f}")
    print(f"  Needs review: {result_strict.needs_review}")
    print(f"  Panels needing review: {sum(1 for p in result_strict.panels if p.needs_review)}")
    
    print(f"Lenient thresholds:")
    print(f"  Document score: {result_lenient.document_score:.3f}")
    print(f"  Needs review: {result_lenient.needs_review}")
    print(f"  Panels needing review: {sum(1 for p in result_lenient.panels if p.needs_review)}")


if __name__ == '__main__':
    print("Scoring Module Test")
    print("=" * 60)
    
    # Run individual field tests
    test_field_scoring()
    
    # Run comprehensive scoring test
    result = test_comprehensive_scoring()
    
    # Test EHR output with scoring
    ehr_data = test_ehr_output_with_scoring()
    
    # Test different thresholds
    test_thresholds()
    
    print("\n" + "="*60)
    print("All scoring tests completed successfully!")
    print(f"Final document score: {result.document_score:.3f}")
    print(f"Review required: {result.needs_review}")
    print(f"Total panels: {len(result.panels)}")
    print(f"Total test rows: {result.total_test_rows}")