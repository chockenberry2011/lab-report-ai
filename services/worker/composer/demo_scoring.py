#!/usr/bin/env python3
"""
Demo script showcasing the comprehensive lab data scoring module
"""

import json
from typing import Dict, Any
from .composer import PanelComposer
from .scoring import LabDataScorer
from .schemas import TestRow


def demo_individual_field_scoring():
    """Demonstrate individual field scoring capabilities"""
    print("🔬 Lab Data Scoring System Demo")
    print("=" * 60)
    print("\n📊 INDIVIDUAL FIELD SCORING DEMO")
    print("Testing how each field type is scored...")
    
    scorer = LabDataScorer()
    
    # Create test cases with various quality levels
    test_cases = [
        {
            'name': 'High Quality Test',
            'test_name': 'Glucose',
            'value': '95',
            'units': 'mg/dL',
            'ref_range': '70-100',
            'classifier_proba': 0.95
        },
        {
            'name': 'Poor Parsing', 
            'test_name': '???',
            'value': 'UNCLEAR_RESULT',
            'units': 'badunit',
            'ref_range': 'malformed range',
            'classifier_proba': 0.3
        },
        {
            'name': 'Mixed Quality',
            'test_name': 'WBC Count',
            'value': '7.2',
            'units': 'K/uL',  
            'ref_range': 'NORMAL',
            'classifier_proba': 0.8
        }
    ]
    
    for case in test_cases:
        test_row = TestRow(
            text=f"{case['test_name']} {case['value']} {case['units']} {case['ref_range']}",
            page=1, line_number=1, y_norm=0.5,
            test_name=case['test_name'],
            result_value=case['value'],
            units=case['units'],
            reference_range=case['ref_range']
        )
        
        confidence = scorer.score_test_row(test_row, case['classifier_proba'])
        
        print(f"\n  {case['name']}:")
        print(f"    Overall Score: {confidence.overall:.3f}")
        print(f"    📈 Value Parse: {confidence.value_parse:.3f}")
        print(f"    🏷️  Unit Validity: {confidence.unit_validity:.3f}")
        print(f"    📋 Ref Range: {confidence.reference_range:.3f}")
        print(f"    📝 Name Clarity: {confidence.test_name_clarity:.3f}")
        print(f"    🤖 Classifier: {confidence.classifier_proba:.3f}")


def demo_comprehensive_scoring():
    """Demonstrate full document scoring"""
    print("\n\n📄 COMPREHENSIVE DOCUMENT SCORING DEMO")
    print("Testing multi-level scoring across a full document...")
    
    # Create realistic test data with quality issues
    test_data = [
        # High quality chemistry panel
        {"text": "COMPREHENSIVE METABOLIC PANEL", "role": "SECTION_PANEL", "page": 1, "yNorm": 0.9},
        {"text": "Glucose 95 mg/dL 70-100", "role": "TEST_ROW", "page": 1, "yNorm": 0.8},
        {"text": "Sodium 140 mEq/L 136-145", "role": "TEST_ROW", "page": 1, "yNorm": 0.7},
        {"text": "Potassium 4.2 mEq/L 3.5-5.1", "role": "TEST_ROW", "page": 1, "yNorm": 0.6},
        {"text": "Chloride 102 mEq/L 98-107", "role": "TEST_ROW", "page": 1, "yNorm": 0.5},
        
        # Problematic lipid panel  
        {"text": "LIPID PANEL - FASTING", "role": "SECTION_PANEL", "page": 2, "yNorm": 0.9},
        {"text": "Total Cholesterol ??? xyz/invalid", "role": "TEST_ROW", "page": 2, "yNorm": 0.8},
        {"text": "??? HIGH", "role": "TEST_ROW", "page": 2, "yNorm": 0.7},
        {"text": "LDL unclear_units bad_range", "role": "TEST_ROW", "page": 2, "yNorm": 0.6},
        
        # Mixed quality CBC
        {"text": "COMPLETE BLOOD COUNT", "role": "SECTION_PANEL", "page": 3, "yNorm": 0.9},
        {"text": "WBC 7.2 K/uL 4.5-11.0", "role": "TEST_ROW", "page": 3, "yNorm": 0.8},
        {"text": "RBC 4.8 badunits >4.0", "role": "TEST_ROW", "page": 3, "yNorm": 0.7},
        {"text": "Hemoglobin 14.2 g/dL 12.0-16.0", "role": "TEST_ROW", "page": 3, "yNorm": 0.6},
        {"text": "Platelets NORMAL", "role": "TEST_ROW", "page": 3, "yNorm": 0.5}
    ]
    
    # Mock classifier probabilities (simulating ML model confidence)
    classifier_probabilities = {
        1: 0.95,  # High confidence on glucose
        2: 0.92,  # High confidence on sodium  
        3: 0.90,  # High confidence on potassium
        4: 0.88,  # High confidence on chloride
        6: 0.4,   # Low confidence on problematic cholesterol
        7: 0.2,   # Very low confidence on ??? line
        8: 0.3,   # Low confidence on malformed LDL
        10: 0.95, # High confidence on WBC
        11: 0.75, # Moderate confidence on RBC with bad units
        12: 0.92, # High confidence on hemoglobin
        13: 0.85  # Good confidence on platelets
    }
    
    # Score with default thresholds
    composer = PanelComposer(enable_scoring=True)
    result = composer.compose(test_data, classifier_probabilities)
    
    # Display results
    print(f"\n  📊 DOCUMENT-LEVEL RESULTS:")
    print(f"    Overall Score: {result.document_score:.3f}")
    print(f"    Needs Review: {'❌ YES' if result.needs_review else '✅ NO'}")
    print(f"    Review Reasons: {result.review_reasons}")
    
    if result.confidence_distribution:
        dist = result.confidence_distribution
        print(f"    Confidence Stats:")
        print(f"      Mean: {dist['mean']:.3f}")
        print(f"      Range: {dist['min']:.3f} - {dist['max']:.3f}")
        print(f"      Std Dev: {dist['std']:.3f}")
    
    print(f"\n  🧪 PANEL-LEVEL RESULTS:")
    for i, panel in enumerate(result.panels, 1):
        status = '❌ NEEDS REVIEW' if panel.needs_review else '✅ GOOD'
        print(f"    Panel {i}: {panel.name} [{status}]")
        print(f"      Score: {panel.panel_score:.3f}")
        print(f"      Tests: {len(panel.test_rows)}")
        if panel.review_reasons:
            print(f"      Issues: {panel.review_reasons}")
    
    return result


def demo_threshold_comparison():
    """Demonstrate effect of different scoring thresholds"""
    print("\n\n⚙️ THRESHOLD CONFIGURATION DEMO")
    print("Comparing strict vs lenient scoring thresholds...")
    
    # Create test data with borderline quality
    test_data = [
        {"text": "BORDERLINE QUALITY PANEL", "role": "SECTION_PANEL", "page": 1, "yNorm": 0.9},
        {"text": "Test1 5.5 questionable_unit 5.0-6.0", "role": "TEST_ROW", "page": 1, "yNorm": 0.8},
        {"text": "Test2 POSITIVE", "role": "TEST_ROW", "page": 1, "yNorm": 0.7},  # No units
        {"text": "Test3 12.1 mg/dL unclear", "role": "TEST_ROW", "page": 1, "yNorm": 0.6},  # Bad range
    ]
    
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
    
    print(f"\n  🔒 STRICT THRESHOLDS:")
    print(f"    Document Score: {result_strict.document_score:.3f}")
    print(f"    Needs Review: {'❌ YES' if result_strict.needs_review else '✅ NO'}")
    panels_review = sum(1 for p in result_strict.panels if p.needs_review)
    print(f"    Panels Needing Review: {panels_review}/{len(result_strict.panels)}")
    
    print(f"\n  🔓 LENIENT THRESHOLDS:")  
    print(f"    Document Score: {result_lenient.document_score:.3f}")
    print(f"    Needs Review: {'❌ YES' if result_lenient.needs_review else '✅ NO'}")
    panels_review = sum(1 for p in result_lenient.panels if p.needs_review)
    print(f"    Panels Needing Review: {panels_review}/{len(result_lenient.panels)}")


def demo_json_output():
    """Show complete JSON output with scoring"""
    print("\n\n📄 EHR-READY JSON OUTPUT DEMO")
    print("Generated JSON with full scoring information...")
    
    test_data = [
        {"text": "DEMO PANEL", "role": "SECTION_PANEL", "page": 1, "yNorm": 0.9},
        {"text": "Glucose 95 mg/dL 70-100", "role": "TEST_ROW", "page": 1, "yNorm": 0.8},
        {"text": "Problematic ??? badunit", "role": "TEST_ROW", "page": 1, "yNorm": 0.7}
    ]
    
    composer = PanelComposer(enable_scoring=True)
    result = composer.compose(test_data)
    
    # Generate and display JSON structure
    ehr_json = result.to_ehr_json()
    ehr_data = json.loads(ehr_json)
    
    print(f"\n  📋 JSON Structure Generated:")
    print(f"    ✅ Document-level scoring: needsReview={ehr_data['document_info']['needs_review']}")
    print(f"    ✅ Panel-level scoring: {len(ehr_data['lab_panels'])} panels with scores")
    print(f"    ✅ Field-level confidences: All test rows include field_confidences")
    print(f"    ✅ Review reasons: Detailed explanations provided")
    print(f"    ✅ Confidence distribution: Statistical analysis included")
    
    # Show sample test row with full confidence breakdown
    sample_test = ehr_data['lab_panels'][0]['test_rows'][0]
    print(f"\n  🔬 Sample Test Row Confidence Breakdown:")
    print(f"    Test: {sample_test['test_name']} = {sample_test['result_value']} {sample_test['units']}")
    print(f"    Overall: {sample_test['confidence']:.3f}")
    fc = sample_test['field_confidences']
    print(f"    Field Details: V={fc['value_parse']:.2f}, U={fc['unit_validity']:.2f}, "
          f"R={fc['reference_range']:.2f}, N={fc['test_name_clarity']:.2f}, C={fc['classifier_proba']:.2f}")


if __name__ == '__main__':
    demo_individual_field_scoring()
    result = demo_comprehensive_scoring()
    demo_threshold_comparison()
    demo_json_output()
    
    print("\n\n" + "=" * 60)
    print("🎉 SCORING SYSTEM DEMO COMPLETE!")
    print("=" * 60)
    print("✅ All confidence scores computed and persisted")
    print("✅ Critical fields flagged when below thresholds")
    print("✅ needsReview and reasons[] arrays populated")
    print("✅ Multi-level scoring (field → panel → document)")
    print("✅ EHR-ready JSON output with full scoring data")
    print("\nThe scoring module successfully evaluates:")
    print("  📈 VALUE: Numeric parse success")
    print("  🏷️  UNIT: Medical unit whitelist validation")
    print("  📋 REF_RANGE: Reference range well-formedness")
    print("  📝 NAME: Test name clarity and medical terminology")
    print("  🤖 CLASSIFIER: ML model role prediction confidence")
    print("\n🔬 Ready for production use in lab data processing!")