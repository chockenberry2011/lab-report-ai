#!/usr/bin/env python3
"""
Prepare training data from Label Studio export

Converts Label Studio JSON export to training format for line role classifier.
"""

import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

try:
    from .line_classifier import LineData, ROLE_LABELS, calculate_y_tertile, detect_header_hints
except ImportError:  # fallback when run as a plain script
    from line_classifier import LineData, ROLE_LABELS, calculate_y_tertile, detect_header_hints


def parse_labelstudio_export(export_path: str) -> List[Dict[str, Any]]:
    """Parse Label Studio JSON export file"""
    with open(export_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        # Single task export
        return [data]
    elif isinstance(data, list):
        # Multiple tasks export
        return data
    else:
        raise ValueError(f"Unexpected export format in {export_path}")


def extract_line_annotations(task: Dict[str, Any]) -> List[LineData]:
    """Extract line data from a single Label Studio task"""
    lines = []
    
    # Get task data
    task_data = task.get('data', {})
    
    # Look for annotations
    annotations = task.get('annotations', [])
    if not annotations:
        print(f"Warning: No annotations found in task {task.get('id', 'unknown')}")
        return lines
    
    # Use the first annotation (or latest if multiple)
    annotation = annotations[-1]  # Use latest annotation
    results = annotation.get('result', [])
    
    # Parse different annotation formats
    for result in results:
        result_type = result.get('type', '')
        
        if result_type == 'choices':
            # Single choice annotation for entire document
            lines.extend(extract_from_choices_annotation(result, task_data))
        elif result_type == 'textarea':
            # Text area with structured data
            lines.extend(extract_from_textarea_annotation(result, task_data))
        elif result_type == 'rectanglelabels':
            # Bounding box annotations
            lines.extend(extract_from_bbox_annotation(result, task_data))
        else:
            print(f"Warning: Unsupported annotation type: {result_type}")
    
    return lines


def extract_from_choices_annotation(result: Dict[str, Any], task_data: Dict[str, Any]) -> List[LineData]:
    """Extract from choice-based annotation (deprecated format)"""
    # This is a fallback for simple choice annotations
    # In practice, you'd want structured line-by-line annotations
    lines = []
    
    text = task_data.get('text', '')
    choice = result.get('value', {}).get('choices', ['SECTION_MISC'])[0]
    
    # Split text into lines and assign the same role to all
    for i, line_text in enumerate(text.split('\n')):
        if line_text.strip():
            line_data = LineData(
                text=line_text.strip(),
                y_tertile=1,  # Default to middle
                is_bold=False,
                is_header_hint=detect_header_hints(line_text),
                role=choice,
                page=1,
                y_norm=0.5
            )
            lines.append(line_data)
    
    return lines


def extract_from_textarea_annotation(result: Dict[str, Any], task_data: Dict[str, Any]) -> List[LineData]:
    """Extract from textarea annotation with JSON structure"""
    lines = []
    
    # Expect structured JSON in textarea
    textarea_value = result.get('value', {}).get('text', '')
    
    try:
        # Parse JSON structure from textarea
        line_data_list = json.loads(textarea_value)
        
        for line_dict in line_data_list:
            # Create LineData from dictionary
            line_data = LineData(
                text=line_dict.get('text', ''),
                y_tertile=calculate_y_tertile(line_dict.get('y_norm', 0.5)),
                is_bold=line_dict.get('is_bold', False),
                is_header_hint=line_dict.get('is_header_hint', detect_header_hints(line_dict.get('text', ''))),
                role=line_dict.get('role', 'SECTION_MISC'),
                page=line_dict.get('page', 1),
                x_left=line_dict.get('x_left', 0.0),
                x_right=line_dict.get('x_right', 100.0),
                y_norm=line_dict.get('y_norm', 0.5),
                font_size=line_dict.get('font_size', 12.0)
            )
            
            # Validate role
            if line_data.role not in ROLE_LABELS:
                print(f"Warning: Unknown role '{line_data.role}', using 'SECTION_MISC'")
                line_data.role = 'SECTION_MISC'
            
            lines.append(line_data)
    
    except json.JSONDecodeError:
        print(f"Warning: Could not parse JSON from textarea annotation")
        # Fallback to treating as plain text
        for line_text in textarea_value.split('\n'):
            if line_text.strip():
                line_data = LineData(
                    text=line_text.strip(),
                    y_tertile=1,
                    is_bold=False,
                    is_header_hint=detect_header_hints(line_text),
                    role='SECTION_MISC',
                    page=1,
                    y_norm=0.5
                )
                lines.append(line_data)
    
    return lines


def extract_from_bbox_annotation(result: Dict[str, Any], task_data: Dict[str, Any]) -> List[LineData]:
    """Extract from bounding box annotations"""
    lines = []
    
    value = result.get('value', {})
    
    # Get bounding box coordinates (Label Studio uses percentages)
    x = value.get('x', 0) / 100.0
    y = value.get('y', 0) / 100.0
    width = value.get('width', 10) / 100.0
    height = value.get('height', 10) / 100.0
    
    # Get label
    labels = value.get('rectanglelabels', ['SECTION_MISC'])
    role = labels[0] if labels else 'SECTION_MISC'
    
    # Get text (might be in original_text or text field)
    text = value.get('text', task_data.get('text', ''))
    
    # Create line data
    line_data = LineData(
        text=text.strip(),
        y_tertile=calculate_y_tertile(1.0 - y),  # Label Studio uses top-down coordinates
        is_bold=False,  # Could be extracted from styling if available
        is_header_hint=detect_header_hints(text),
        role=role,
        page=1,
        x_left=x * 100,
        x_right=(x + width) * 100,
        y_norm=1.0 - y,  # Convert to bottom-up
        font_size=12.0  # Default, could be extracted if available
    )
    
    # Validate role
    if line_data.role not in ROLE_LABELS:
        print(f"Warning: Unknown role '{line_data.role}', using 'SECTION_MISC'")
        line_data.role = 'SECTION_MISC'
    
    lines.append(line_data)
    return lines


def validate_training_data(lines: List[LineData]) -> Dict[str, Any]:
    """Validate and analyze training data"""
    stats = {
        'total_lines': len(lines),
        'role_distribution': {},
        'y_tertile_distribution': {},
        'bold_count': 0,
        'header_hint_count': 0,
        'pages': set(),
        'validation_errors': []
    }
    
    for line in lines:
        # Role distribution
        stats['role_distribution'][line.role] = stats['role_distribution'].get(line.role, 0) + 1
        
        # Y tertile distribution
        stats['y_tertile_distribution'][line.y_tertile] = stats['y_tertile_distribution'].get(line.y_tertile, 0) + 1
        
        # Feature counts
        if line.is_bold:
            stats['bold_count'] += 1
        if line.is_header_hint:
            stats['header_hint_count'] += 1
        
        # Pages
        stats['pages'].add(line.page)
        
        # Validation
        if not line.text.strip():
            stats['validation_errors'].append(f"Empty text in line")
        
        if line.role not in ROLE_LABELS:
            stats['validation_errors'].append(f"Invalid role: {line.role}")
        
        if not (0 <= line.y_norm <= 1):
            stats['validation_errors'].append(f"Invalid y_norm: {line.y_norm}")
        
        if line.y_tertile not in [0, 1, 2]:
            stats['validation_errors'].append(f"Invalid y_tertile: {line.y_tertile}")
    
    stats['pages'] = len(stats['pages'])
    return stats


def save_training_data(lines: List[LineData], output_path: str):
    """Save training data to JSON file"""
    data = []
    for line in lines:
        line_dict = {
            'text': line.text,
            'y_tertile': line.y_tertile,
            'is_bold': line.is_bold,
            'is_header_hint': line.is_header_hint,
            'role': line.role,
            'page': line.page,
            'x_left': line.x_left,
            'x_right': line.x_right,
            'y_norm': line.y_norm,
            'font_size': line.font_size
        }
        data.append(line_dict)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Training data saved to {output_path}")


def load_training_data(input_path: str) -> List[LineData]:
    """Load training data from JSON file"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    lines = []
    for line_dict in data:
        line_data = LineData(**line_dict)
        lines.append(line_data)
    
    return lines


def main():
    parser = argparse.ArgumentParser(description='Prepare training data from Label Studio export')
    parser.add_argument('export_file', help='Path to Label Studio export JSON file')
    parser.add_argument('--output', '-o', default='/data/training/roles_training_data.json',
                       help='Output path for training data')
    parser.add_argument('--validate', action='store_true',
                       help='Validate and show statistics for training data')
    
    args = parser.parse_args()
    
    if not Path(args.export_file).exists():
        print(f"Error: Export file not found: {args.export_file}")
        sys.exit(1)
    
    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Processing Label Studio export: {args.export_file}")
    
    # Parse export
    tasks = parse_labelstudio_export(args.export_file)
    print(f"Found {len(tasks)} tasks in export")
    
    # Extract all lines
    all_lines = []
    for i, task in enumerate(tasks):
        lines = extract_line_annotations(task)
        all_lines.extend(lines)
        print(f"Task {i+1}: extracted {len(lines)} lines")
    
    print(f"Total extracted lines: {len(all_lines)}")
    
    if not all_lines:
        print("Error: No lines extracted from export file")
        sys.exit(1)
    
    # Validate data
    stats = validate_training_data(all_lines)
    
    print("\n=== Training Data Statistics ===")
    print(f"Total lines: {stats['total_lines']}")
    print(f"Pages: {stats['pages']}")
    print(f"Lines with bold: {stats['bold_count']}")
    print(f"Lines with header hints: {stats['header_hint_count']}")
    
    print(f"\nRole distribution:")
    for role, count in sorted(stats['role_distribution'].items()):
        percentage = (count / stats['total_lines']) * 100
        print(f"  {role}: {count} ({percentage:.1f}%)")
    
    print(f"\nY-tertile distribution:")
    tertile_names = {0: 'bottom', 1: 'middle', 2: 'top'}
    for tertile, count in sorted(stats['y_tertile_distribution'].items()):
        percentage = (count / stats['total_lines']) * 100
        print(f"  {tertile_names[tertile]}: {count} ({percentage:.1f}%)")
    
    if stats['validation_errors']:
        print(f"\n⚠️  Validation errors ({len(stats['validation_errors'])}):")
        for error in stats['validation_errors'][:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(stats['validation_errors']) > 10:
            print(f"  ... and {len(stats['validation_errors']) - 10} more")
    
    # Check for class imbalance
    role_counts = list(stats['role_distribution'].values())
    if role_counts:
        min_count = min(role_counts)
        max_count = max(role_counts)
        imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
        
        if imbalance_ratio > 10:
            print(f"\n⚠️  High class imbalance detected (ratio: {imbalance_ratio:.1f})")
            print("Consider collecting more data for underrepresented classes")
    
    if args.validate:
        print("\nValidation complete. Exiting without saving.")
        sys.exit(0)
    
    # Save training data
    save_training_data(all_lines, args.output)
    
    print(f"\n✅ Training data preparation complete!")
    print(f"Next steps:")
    print(f"  1. Review the statistics above")
    print(f"  2. Run training: python train_roles.py {args.output}")
    print(f"  3. Evaluate model: python eval_roles.py")


if __name__ == '__main__':
    main()