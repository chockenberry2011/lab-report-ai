#!/usr/bin/env python3
"""
Dev-only CLI for sanity-checking roles model output

Usage:
    python -m services.trainer.roles.dev_sanity /data/outbox/<file>.lines.json --model-dir /models/roles
"""

import os
import sys
import json
import argparse
from pathlib import Path
from collections import Counter
from typing import List, Dict, Any

def load_lines_json(file_path: str) -> List[Dict]:
    """Load lines from JSON file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different JSON structures
    if isinstance(data, dict):
        if 'lines' in data:
            return data['lines']
        elif 'extraction_result' in data and 'lines' in data['extraction_result']:
            return data['extraction_result']['lines']
        else:
            # Assume the dict itself contains line data
            return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"Unsupported JSON structure in {file_path}")

def run_roles_model(lines: List[Dict], model_dir: str) -> List[Dict]:
    """Run roles model on lines and return enriched results"""
    try:
        # Import the runtime inference module
        import sys
        import os
        
        # Add paths to ensure we can import services
        sys.path.insert(0, '/app')
        sys.path.insert(0, '/app/services')
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))
        
        try:
            from services.worker.runtime.roles_infer import predict_line_roles, Line
        except ImportError:
            # Try alternative import path
            from worker.runtime.roles_infer import predict_line_roles, Line
        
        # Convert to Line objects
        line_objects = []
        for line_data in lines:
            line_obj = Line(
                text=line_data.get('text', ''),
                y_tertile=line_data.get('y_tertile', 0),
                is_bold=line_data.get('is_bold', line_data.get('isBold', False)),
                is_header_hint=line_data.get('is_header_hint', False),
                font_size=line_data.get('font_size', line_data.get('fontSize', 12.0)),
                x_left=line_data.get('x_left', line_data.get('xLeft', 0.0)),
                width=line_data.get('width', line_data.get('xRight', 0.0) - line_data.get('xLeft', 0.0)),
                page=line_data.get('page', 1)
            )
            line_objects.append(line_obj)
        
        # Run model inference
        print(f"Running roles model inference on {len(line_objects)} lines...")
        predictions = predict_line_roles(line_objects, model_dir)
        
        # Enrich original lines with predictions
        enriched_lines = []
        for i, (original_line, prediction) in enumerate(zip(lines, predictions)):
            enriched_line = original_line.copy()
            enriched_line['role'] = prediction.predicted_role
            enriched_line['role_prob'] = float(prediction.confidence)
            enriched_line['predicted_role'] = prediction.predicted_role  # Keep for compatibility
            enriched_line['role_probabilities'] = prediction.probabilities
            enriched_lines.append(enriched_line)
        
        return enriched_lines
        
    except Exception as e:
        print(f"Error running roles model: {e}")
        import traceback
        traceback.print_exc()
        return []

def print_role_summary(enriched_lines: List[Dict]):
    """Print summary of role classifications"""
    # Count roles
    role_counts = Counter()
    for line in enriched_lines:
        role = line.get('role', 'UNKNOWN')
        role_counts[role] += 1
    
    print("\n" + "="*50)
    print("ROLE DISTRIBUTION (Top 10)")
    print("="*50)
    for role, count in role_counts.most_common(10):
        percentage = (count / len(enriched_lines)) * 100
        print(f"{role:20} {count:6} ({percentage:5.1f}%)")
    
    print(f"\nTotal lines processed: {len(enriched_lines)}")

def print_section_panels(enriched_lines: List[Dict]):
    """Print first 10 SECTION_PANEL lines"""
    print("\n" + "="*50)
    print("SECTION_PANEL LINES (First 10)")
    print("="*50)
    
    panel_lines = [line for line in enriched_lines if line.get('role') == 'SECTION_PANEL']
    
    if not panel_lines:
        print("No SECTION_PANEL lines found")
        return
    
    for i, line in enumerate(panel_lines[:10]):
        page = line.get('page', 'N/A')
        text = line.get('text', '').strip()
        prob = line.get('role_prob', 0.0)
        print(f"{i+1:2}. Page {page:2} | {prob:.3f} | {text[:80]}")
    
    if len(panel_lines) > 10:
        print(f"... and {len(panel_lines) - 10} more SECTION_PANEL lines")

def print_test_rows(enriched_lines: List[Dict]):
    """Print first 10 TEST_ROW lines"""
    print("\n" + "="*50)
    print("TEST_ROW LINES (First 10)")
    print("="*50)
    
    test_lines = [line for line in enriched_lines if line.get('role') == 'TEST_ROW']
    
    if not test_lines:
        print("No TEST_ROW lines found")
        return
    
    for i, line in enumerate(test_lines[:10]):
        page = line.get('page', 'N/A')
        text = line.get('text', '').strip()
        prob = line.get('role_prob', 0.0)
        print(f"{i+1:2}. Page {page:2} | {prob:.3f} | {text[:80]}")
    
    if len(test_lines) > 10:
        print(f"... and {len(test_lines) - 10} more TEST_ROW lines")

def write_debug_file(enriched_lines: List[Dict], input_file: str):
    """Write enriched lines to debug file"""
    input_path = Path(input_file)
    output_path = input_path.parent / f"{input_path.stem}.roles.sanity.json"
    
    debug_data = {
        "metadata": {
            "source_file": str(input_path),
            "total_lines": len(enriched_lines),
            "model_dir": model_dir,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        },
        "role_distribution": dict(Counter(line.get('role', 'UNKNOWN') for line in enriched_lines)),
        "lines": enriched_lines
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(debug_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Debug file written: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Sanity-check roles model output")
    parser.add_argument("input_file", help="Path to lines JSON file")
    parser.add_argument("--model-dir", default="/models/roles", help="Path to roles model directory")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.input_file):
        print(f"Error: Input file not found: {args.input_file}")
        sys.exit(1)
    
    if not os.path.exists(args.model_dir):
        print(f"Error: Model directory not found: {args.model_dir}")
        sys.exit(1)
    
    global model_dir
    model_dir = args.model_dir
    
    print(f"🔍 Loading lines from: {args.input_file}")
    lines = load_lines_json(args.input_file)
    print(f"📋 Loaded {len(lines)} lines")
    
    print(f"🤖 Running roles model from: {args.model_dir}")
    enriched_lines = run_roles_model(lines, args.model_dir)
    
    if not enriched_lines:
        print("❌ Failed to run roles model")
        sys.exit(1)
    
    # Print summaries
    print_role_summary(enriched_lines)
    print_section_panels(enriched_lines)
    print_test_rows(enriched_lines)
    
    # Write debug file
    write_debug_file(enriched_lines, args.input_file)
    
    print("\n✅ Roles sanity check completed!")

if __name__ == "__main__":
    main()