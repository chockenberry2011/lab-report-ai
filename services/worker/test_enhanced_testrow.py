#!/usr/bin/env python3
"""
Demo for enhanced tag_testrow_line function
"""

import sys
import re

def demo_tag_testrow_line():
    """Demo the enhanced test row parsing"""
    
    # Mock the tag_testrow_line function for demo purposes
    def mock_enhanced_testrow_parser(text: str):
        """Mock implementation showing enhanced parsing"""
        
        # Basic parsed fields (simulated)
        parsed = {
            'test_names': [],
            'values': [],
            'units': [],
            'ref_ranges': [],
            'flags': []
        }
        
        # Simple mock parsing for demo
        if 'Glucose' in text:
            parsed['test_names'] = ['Glucose']
            parsed['values'] = ['95']
            parsed['units'] = ['mg/dL']
            parsed['ref_ranges'] = ['70-100']
        elif 'HDL' in text:
            parsed['test_names'] = ['HDL']
            parsed['values'] = ['65']
            parsed['units'] = ['mg/dL']
            parsed['ref_ranges'] = ['>40']
            parsed['flags'] = ['H']
        elif 'Creatinine' in text:
            parsed['test_names'] = ['Creatinine']
            parsed['values'] = ['1.2']
            parsed['units'] = ['mg/dL']
            parsed['ref_ranges'] = ['0.8-1.2']
        
        # NEW: Enhanced field extraction (same logic as in tasks.py)
        try:
            # Extract LOINC/CPT codes
            codes = {}
            code_pattern = re.compile(r'\b(LOINC|CPT)\s*[:#]?\s*([A-Z0-9-]+)\b', re.IGNORECASE)
            code_matches = code_pattern.findall(text)
            for code_type, code_value in code_matches:
                codes[code_type.lower()] = code_value
            if codes:
                parsed['codes'] = codes
            
            # Extract methodology using keywords
            method_patterns = [
                r'(?:Method|Methodology)[\s:]*([^,\n]+)',
                r'\b(Immunoassay|LC/MS-MS|LC-MS|HPLC|RIA|ELISA|PCR|Flow Cytometry|Microscopy)\b'
            ]
            for pattern in method_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    parsed['methodology'] = match.group(1).strip()
                    break
            
            # Extract observation time
            time_patterns = [
                r'\b(\d{1,2}:\d{2}\s*(?:AM|PM))\b',  # 12-hour format
                r'\b(\d{1,2}:\d{2})\b'  # 24-hour format
            ]
            for pattern in time_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    time_str = match.group(1)
                    parsed['observed_at'] = time_str
                    break
            
            # Extract comments/notes - simplified for demo
            comment_indicators = ['elevated', 'normal', 'good levels', 'repeat test', 'fasting required']
            for indicator in comment_indicators:
                if indicator.lower() in text.lower():
                    parsed['comments'] = indicator.capitalize()
                    break
                    
        except Exception:
            # Don't crash if enhanced extraction fails
            pass
        
        return {
            "text": text,
            "tokens": [],  # Simplified for demo
            "parsed_fields": parsed
        }
    
    # Test cases
    test_lines = [
        "Glucose    95    mg/dL    70-100    LOINC: 2345-7    Method: Enzymatic    09:30 AM",
        "HDL H    65    mg/dL    >40    CPT: 83718    Good levels obtained",
        "Creatinine    1.2    mg/dL    0.8-1.2    LC/MS-MS    Slightly elevated    14:30",
        "Hemoglobin A1C    6.5    %    <7.0    Immunoassay",
        "Basic test without extras    Normal    No codes or methods here"
    ]
    
    print("=== Enhanced tag_testrow_line Demo ===")
    
    for i, test_line in enumerate(test_lines, 1):
        print(f"\n--- Test {i} ---")
        print(f"Input: {test_line}")
        
        result = mock_enhanced_testrow_parser(test_line)
        parsed = result['parsed_fields']
        
        print("Basic fields:")
        if parsed.get('test_names'):
            print(f"  Test: {parsed['test_names'][0]}")
        if parsed.get('values'):
            print(f"  Value: {parsed['values'][0]}")
        if parsed.get('units'):
            print(f"  Unit: {parsed['units'][0]}")
        if parsed.get('ref_ranges'):
            print(f"  Range: {parsed['ref_ranges'][0]}")
        if parsed.get('flags'):
            print(f"  Flag: {parsed['flags'][0]}")
        
        print("Enhanced fields:")
        if parsed.get('codes'):
            codes_str = ", ".join(f"{k.upper()}: {v}" for k, v in parsed['codes'].items())
            print(f"  Codes: {codes_str}")
        else:
            print("  Codes: (none)")
            
        if parsed.get('methodology'):
            print(f"  Method: {parsed['methodology']}")
        else:
            print("  Method: (none)")
            
        if parsed.get('observed_at'):
            print(f"  Time: {parsed['observed_at']}")
        else:
            print("  Time: (none)")
            
        if parsed.get('comments'):
            print(f"  Comments: {parsed['comments']}")
        else:
            print("  Comments: (none)")
    
    print("\n=== Complete parsed_fields Structure ===")
    # Show complete structure for last test case
    import json
    print(json.dumps(result['parsed_fields'], indent=2))
    
    print("\n✅ Enhanced tag_testrow_line demonstrated!")
    print("New optional keys added: 'codes', 'methodology', 'comments', 'observed_at'")
    print("Function does NOT crash when labels absent - keys are simply omitted.")

if __name__ == "__main__":
    demo_tag_testrow_line()