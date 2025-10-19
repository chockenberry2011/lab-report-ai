#!/usr/bin/env python3
"""
Test script for enhanced composer functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Fix relative imports by importing directly
from schemas import Panel, TestRow, ComposerResult
from panel_headers import score_panel_header  
from scoring import LabDataScorer

# Import composer after fixing sys path
import composer
from composer import PanelComposer
import json

def test_enhanced_composer():
    """Test the enhanced composer with toy data"""
    
    # Create toy lines data with enhanced content
    lines_data = [
        {
            "text": "BASIC METABOLIC PANEL *",
            "role": "SECTION_PANEL",
            "predicted_role": "SECTION_PANEL",
            "page": 1,
            "line_number": 0,
            "xLeft": 0.1,
            "x_left": 0.1,
            "yNorm": 0.2,
            "y_norm": 0.2,
            "fontSize": 12.0,
            "isBold": True
        },
        {
            "text": "* Reference ranges vary by laboratory LOINC: 24323-8",
            "role": "JUNK",
            "predicted_role": "JUNK", 
            "page": 1,
            "line_number": 1,
            "xLeft": 0.1,
            "x_left": 0.1,
            "yNorm": 0.25,
            "y_norm": 0.25,
            "fontSize": 10.0,
            "isBold": False
        },
        {
            "text": "Glucose    95    mg/dL    70-100    Method: Immunoassay    09:30 AM",
            "role": "TEST_ROW",
            "predicted_role": "TEST_ROW",
            "page": 1,
            "line_number": 2,
            "xLeft": 0.1,
            "x_left": 0.1,
            "yNorm": 0.3,
            "y_norm": 0.3,
            "fontSize": 10.0,
            "isBold": False
        },
        {
            "text": "Sodium H    145    mEq/L    135-145    CPT: 84295",
            "role": "TEST_ROW", 
            "predicted_role": "TEST_ROW",
            "page": 1,
            "line_number": 3,
            "xLeft": 0.1,
            "x_left": 0.1,
            "yNorm": 0.35,
            "y_norm": 0.35,
            "fontSize": 10.0,
            "isBold": False
        },
        {
            "text": "Creatinine    1.2    mg/dL    0.8-1.2    LC/MS-MS    Slightly elevated    10:15 AM",
            "role": "TEST_ROW",
            "predicted_role": "TEST_ROW", 
            "page": 1,
            "line_number": 4,
            "xLeft": 0.1,
            "x_left": 0.1,
            "yNorm": 0.4,
            "y_norm": 0.4,
            "fontSize": 10.0,
            "isBold": False
        }
    ]
    
    # Create composer instance
    composer = PanelComposer(enable_scoring=True)
    
    # Compose the data
    result = composer.compose(lines_data)
    
    print("=== Enhanced Composer Test Results ===")
    print(f"Found {len(result.panels)} panels")
    print(f"Total test rows: {result.total_test_rows}")
    
    for i, panel in enumerate(result.panels):
        print(f"\n--- Panel {i+1}: {panel.name} ---")
        
        # Show enhanced panel fields
        if hasattr(panel, 'panel_code') and panel.panel_code:
            print(f"Panel Code: {panel.panel_code}")
        if hasattr(panel, 'comments') and panel.comments:
            print(f"Panel Comments: {panel.comments}")
            
        print(f"Tests: {len(panel.test_rows)}")
        
        for j, test_row in enumerate(panel.test_rows):
            print(f"  Test {j+1}: {test_row.test_name} = {test_row.result_value} {test_row.units or ''}")
            
            # Show enhanced test row fields
            if hasattr(test_row, 'codes') and test_row.codes:
                codes_str = ", ".join(f"{k.upper()}: {v}" for k, v in test_row.codes.items())
                print(f"    Codes: {codes_str}")
                
            if hasattr(test_row, 'methodology') and test_row.methodology:
                print(f"    Method: {test_row.methodology}")
                
            if hasattr(test_row, 'observed_at') and test_row.observed_at:
                print(f"    Time: {test_row.observed_at}")
                
            if hasattr(test_row, 'comments') and test_row.comments:
                print(f"    Comments: {test_row.comments}")
                
            print(f"    Confidence: {test_row.confidence:.3f}")
    
    # Show overall document score
    if hasattr(result, 'document_score') and result.document_score:
        print(f"\nDocument Score: {result.document_score:.3f}")
        print(f"Needs Review: {result.needs_review}")
        
    # Convert to dict and show structure
    panel_dicts = [panel.to_dict() for panel in result.panels]
    print(f"\n=== Sample Panel Dict Structure ===")
    if panel_dicts:
        # Show first panel structure with indentation
        print(json.dumps(panel_dicts[0], indent=2, default=str))

if __name__ == "__main__":
    test_enhanced_composer()