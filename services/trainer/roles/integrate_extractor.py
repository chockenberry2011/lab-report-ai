#!/usr/bin/env python3
"""
Integration with extractor service

Processes PDF extraction output and applies role classification.
"""

import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from .line_classifier import LineRoleClassifier, LineData, calculate_y_tertile, detect_header_hints
except ImportError:  # fallback when run as a plain script
    from line_classifier import LineRoleClassifier, LineData, calculate_y_tertile, detect_header_hints


def convert_extractor_output_to_lines(extractor_output: Dict[str, Any]) -> List[LineData]:
    """Convert extractor service output to LineData objects"""
    lines = []
    
    for line_dict in extractor_output.get('lines', []):
        # Extract features
        text = line_dict.get('text', '').strip()
        if not text:
            continue
        
        y_norm = line_dict.get('yNorm', 0.5)
        y_tertile = calculate_y_tertile(y_norm)
        is_bold = line_dict.get('isBold', False)
        is_header_hint = detect_header_hints(text)
        
        line_data = LineData(
            text=text,
            y_tertile=y_tertile,
            is_bold=is_bold,
            is_header_hint=is_header_hint,
            role='UNKNOWN',  # Will be predicted
            page=line_dict.get('page', 1),
            x_left=line_dict.get('xLeft', 0.0),
            x_right=line_dict.get('xRight', 100.0),
            y_norm=y_norm,
            font_size=line_dict.get('fontSize', 12.0)
        )
        
        lines.append(line_data)
    
    return lines


def apply_role_classification(lines: List[LineData], classifier: LineRoleClassifier) -> List[Dict[str, Any]]:
    """Apply role classification to lines and return enriched data"""
    if not lines:
        return []
    
    # Get predictions and probabilities
    predictions = classifier.predict(lines)
    probabilities = classifier.predict_proba(lines)
    
    enriched_lines = []
    
    for i, line in enumerate(lines):
        # Get top 3 predictions
        line_probs = probabilities[i]
        sorted_indices = line_probs.argsort()[::-1]
        
        top_predictions = []
        for j in range(min(3, len(sorted_indices))):
            idx = sorted_indices[j]
            role = classifier.label_encoder.classes_[idx]
            confidence = float(line_probs[idx])
            top_predictions.append({
                'role': role,
                'confidence': confidence
            })
        
        # Create enriched line data
        enriched_line = {
            'text': line.text,
            'page': line.page,
            'xLeft': line.x_left,
            'xRight': line.x_right,
            'yNorm': line.y_norm,
            'fontSize': line.font_size,
            'isBold': line.is_bold,
            'hasText': True,
            'source': 'pdf',  # Assume from extractor
            
            # Role classification results
            'predicted_role': predictions[i],
            'confidence': float(line_probs.max()),
            'top_predictions': top_predictions,
            
            # Features used for classification
            'features': {
                'y_tertile': line.y_tertile,
                'is_bold': line.is_bold,
                'is_header_hint': line.is_header_hint
            }
        }
        
        enriched_lines.append(enriched_line)
    
    return enriched_lines


def process_extracted_document(input_path: str, classifier: LineRoleClassifier, 
                              output_path: Optional[str] = None) -> Dict[str, Any]:
    """Process a document from extractor output"""
    
    # Load extractor output
    with open(input_path, 'r', encoding='utf-8') as f:
        extractor_output = json.load(f)
    
    print(f"Processing {extractor_output.get('total_lines', 0)} lines from {input_path}")
    
    # Convert to LineData objects
    lines = convert_extractor_output_to_lines(extractor_output)
    
    if not lines:
        print("No valid lines found in extractor output")
        return {}
    
    print(f"Converted {len(lines)} lines for role classification")
    
    # Apply role classification
    enriched_lines = apply_role_classification(lines, classifier)
    
    # Calculate statistics
    role_counts = {}
    confidence_scores = []
    
    for line in enriched_lines:
        role = line['predicted_role']
        role_counts[role] = role_counts.get(role, 0) + 1
        confidence_scores.append(line['confidence'])
    
    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
    
    # Create output document
    output_document = {
        'source_file': extractor_output.get('source_file', 'unknown'),
        'total_lines': len(enriched_lines),
        'pages': extractor_output.get('pages', 1),
        'processing_metadata': {
            'has_role_classification': True,
            'average_confidence': avg_confidence,
            'role_distribution': role_counts
        },
        'lines': enriched_lines
    }
    
    # Save if output path specified
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_document, f, indent=2, ensure_ascii=False)
        
        print(f"Role-classified document saved to {output_path}")
    
    # Print statistics
    print(f"\nRole classification results:")
    print(f"  Average confidence: {avg_confidence:.3f}")
    print(f"  Role distribution:")
    for role, count in sorted(role_counts.items()):
        percentage = (count / len(enriched_lines)) * 100
        print(f"    {role}: {count} ({percentage:.1f}%)")
    
    return output_document


def batch_process_directory(input_dir: str, classifier: LineRoleClassifier, 
                           output_dir: str, pattern: str = "*.lines.json"):
    """Process all extractor output files in a directory"""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    
    if not input_path.exists():
        print(f"Input directory not found: {input_dir}")
        return
    
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Find all matching files
    files = list(input_path.glob(pattern))
    
    if not files:
        print(f"No files matching '{pattern}' found in {input_dir}")
        return
    
    print(f"Processing {len(files)} files from {input_dir}")
    
    for file_path in files:
        print(f"\n--- Processing {file_path.name} ---")
        
        # Generate output filename
        output_filename = file_path.stem + ".roles.json"
        output_file_path = output_path / output_filename
        
        try:
            process_extracted_document(
                str(file_path),
                classifier,
                str(output_file_path)
            )
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
    
    print(f"\nBatch processing completed. Results in {output_dir}")


def main():
    parser = argparse.ArgumentParser(description='Apply role classification to extractor output')
    parser.add_argument('--model-dir', default='/models/roles',
                       help='Directory containing trained role classifier')
    parser.add_argument('--input', 
                       help='Input file (extractor JSON output) or directory')
    parser.add_argument('--output',
                       help='Output file or directory')
    parser.add_argument('--batch', action='store_true',
                       help='Process all files in input directory')
    parser.add_argument('--pattern', default='*.lines.json',
                       help='File pattern for batch processing')
    
    args = parser.parse_args()
    
    if not args.input:
        print("Error: --input is required")
        return
    
    # Load classifier
    model_dir = Path(args.model_dir)
    if not model_dir.exists():
        print(f"Error: Model directory not found: {model_dir}")
        return
    
    print(f"Loading role classifier from {model_dir}")
    
    try:
        classifier = LineRoleClassifier()
        classifier.load_model(model_dir)
        print("Role classifier loaded successfully")
    except Exception as e:
        print(f"Error loading classifier: {e}")
        return
    
    # Process files
    input_path = Path(args.input)
    
    if args.batch or input_path.is_dir():
        # Batch processing
        if not args.output:
            output_dir = str(input_path.parent / "role_classified")
        else:
            output_dir = args.output
        
        batch_process_directory(
            str(input_path),
            classifier,
            output_dir,
            args.pattern
        )
    
    else:
        # Single file processing
        if not input_path.exists():
            print(f"Error: Input file not found: {args.input}")
            return
        
        output_file = args.output
        if not output_file:
            # Generate default output filename
            output_file = str(input_path.parent / (input_path.stem + ".roles.json"))
        
        process_extracted_document(
            str(input_path),
            classifier,
            output_file
        )


if __name__ == '__main__':
    main()