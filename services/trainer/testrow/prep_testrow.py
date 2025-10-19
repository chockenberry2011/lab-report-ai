#!/usr/bin/env python3
"""
Prepare TEST_ROW token classification data from Label Studio export

Converts Label Studio NER annotations to training format.
"""

import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

try:
    from .token_classifier import TOKEN_LABELS
    from .rule_splitter import RuleBasedSplitter
except ImportError:  # fallback when run as a plain script
    from token_classifier import TOKEN_LABELS
    from rule_splitter import RuleBasedSplitter


def parse_labelstudio_export(export_path: str) -> List[Dict[str, Any]]:
    """Parse Label Studio JSON export file"""
    with open(export_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if isinstance(data, dict):
        return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"Unexpected export format in {export_path}")


def extract_token_annotations(task: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    """Extract token-level annotations from Label Studio task"""
    examples = []
    
    # Get task data
    text = task.get('data', {}).get('text', '')
    if not text.strip():
        return examples
    
    # Get annotations
    annotations = task.get('annotations', [])
    if not annotations:
        print(f"Warning: No annotations found in task {task.get('id', 'unknown')}")
        return examples
    
    # Use the latest annotation
    annotation = annotations[-1]
    results = annotation.get('result', [])
    
    if not results:
        print(f"Warning: No results in annotation for task {task.get('id', 'unknown')}")
        return examples
    
    # Process different annotation types
    for result in results:
        result_type = result.get('type', '')
        
        if result_type == 'labels':
            # NER-style span annotations
            examples.extend(extract_from_span_labels(result, text))
        elif result_type == 'textarea':
            # JSON format in text area
            examples.extend(extract_from_textarea_format(result, text))
        elif result_type == 'choices':
            # Fallback to rule-based splitting
            examples.extend(extract_with_rule_fallback(result, text))
        else:
            print(f"Warning: Unsupported annotation type: {result_type}")
    
    return examples


def extract_from_span_labels(result: Dict[str, Any], text: str) -> List[Tuple[str, List[str]]]:
    """Extract from NER span-based annotations"""
    value = result.get('value', {})
    
    # Get span information
    start = value.get('start', 0)
    end = value.get('end', len(text))
    labels = value.get('labels', ['O'])
    
    # Extract the span text
    span_text = text[start:end]
    
    if not span_text.strip():
        return []
    
    # For now, create simple token-level labels
    # In a real implementation, you'd want more sophisticated span handling
    words = span_text.split()
    
    # Assign BIO labels
    if len(words) == 0:
        return []
    elif len(words) == 1:
        token_labels = [f'B-{labels[0]}' if labels[0] != 'O' else 'O']
    else:
        token_labels = [f'B-{labels[0]}' if labels[0] != 'O' else 'O']
        token_labels.extend([f'I-{labels[0]}' if labels[0] != 'O' else 'O'] * (len(words) - 1))
    
    return [(span_text, token_labels)]


def extract_from_textarea_format(result: Dict[str, Any], original_text: str) -> List[Tuple[str, List[str]]]:
    """Extract from structured JSON in textarea"""
    examples = []
    
    textarea_value = result.get('value', {}).get('text', '')
    
    try:
        # Parse JSON structure
        annotation_data = json.loads(textarea_value)
        
        if isinstance(annotation_data, dict):
            # Single example
            examples.append(parse_single_annotation(annotation_data))
        elif isinstance(annotation_data, list):
            # Multiple examples
            for item in annotation_data:
                examples.append(parse_single_annotation(item))
    
    except json.JSONDecodeError:
        print(f"Warning: Could not parse JSON from textarea")
        # Treat as plain text with rule-based fallback
        examples.extend(extract_with_rule_fallback({'value': {'choices': ['TEST_ROW']}}, textarea_value))
    
    return examples


def parse_single_annotation(annotation: Dict[str, Any]) -> Tuple[str, List[str]]:
    """Parse a single annotation record"""
    text = annotation.get('text', '').strip()
    labels = annotation.get('labels', [])
    
    words = text.split()
    
    # Handle different label formats
    if isinstance(labels, list):
        if len(labels) == len(words):
            # Direct word-to-label mapping
            token_labels = labels
        elif len(labels) == 1:
            # Single label for entire text - use rule-based splitting
            splitter = RuleBasedSplitter()
            token_labels = splitter.parse_to_bio_labels(text)
        else:
            # Length mismatch - pad or truncate
            token_labels = labels[:len(words)] + ['O'] * max(0, len(words) - len(labels))
    else:
        # Fallback to rule-based
        splitter = RuleBasedSplitter()
        token_labels = splitter.parse_to_bio_labels(text)
    
    # Validate labels
    validated_labels = []
    for label in token_labels:
        if label in TOKEN_LABELS:
            validated_labels.append(label)
        else:
            print(f"Warning: Unknown label '{label}', using 'O'")
            validated_labels.append('O')
    
    return (text, validated_labels)


def extract_with_rule_fallback(result: Dict[str, Any], text: str) -> List[Tuple[str, List[str]]]:
    """Use rule-based splitter as fallback"""
    if not text.strip():
        return []
    
    splitter = RuleBasedSplitter()
    labels = splitter.parse_to_bio_labels(text)
    
    return [(text, labels)]


def validate_training_data(examples: List[Tuple[str, List[str]]]) -> Dict[str, Any]:
    """Validate and analyze training data"""
    stats = {
        'total_examples': len(examples),
        'total_tokens': 0,
        'label_distribution': {},
        'entity_distribution': {},
        'validation_errors': [],
        'avg_tokens_per_example': 0,
        'examples_by_length': {}
    }
    
    entity_types = set()
    all_tokens = []
    
    for i, (text, labels) in enumerate(examples):
        words = text.split()
        
        # Validate length match
        if len(words) != len(labels):
            stats['validation_errors'].append(
                f"Example {i}: Length mismatch - {len(words)} words, {len(labels)} labels"
            )
            continue
        
        # Count tokens and labels
        stats['total_tokens'] += len(labels)
        all_tokens.extend(labels)
        
        # Track example length
        length_bin = len(words) // 10 * 10  # Group by 10s
        stats['examples_by_length'][f'{length_bin}-{length_bin+9}'] = \
            stats['examples_by_length'].get(f'{length_bin}-{length_bin+9}', 0) + 1
        
        # Extract entity types
        for label in labels:
            if label.startswith('B-') or label.startswith('I-'):
                entity_type = label[2:]
                entity_types.add(entity_type)
        
        # Validate individual labels
        for j, label in enumerate(labels):
            if label not in TOKEN_LABELS:
                stats['validation_errors'].append(
                    f"Example {i}, token {j}: Invalid label '{label}'"
                )
    
    # Calculate label distribution
    for label in TOKEN_LABELS:
        count = all_tokens.count(label)
        stats['label_distribution'][label] = {
            'count': count,
            'percentage': (count / len(all_tokens) * 100) if all_tokens else 0
        }
    
    # Calculate entity distribution
    for entity_type in entity_types:
        b_count = all_tokens.count(f'B-{entity_type}')
        i_count = all_tokens.count(f'I-{entity_type}')
        stats['entity_distribution'][entity_type] = {
            'entities': b_count,  # B- tags indicate entity count
            'tokens': b_count + i_count
        }
    
    # Calculate averages
    if examples:
        stats['avg_tokens_per_example'] = stats['total_tokens'] / len(examples)
    
    return stats


def save_training_data(examples: List[Tuple[str, List[str]]], output_path: str):
    """Save training data in format expected by trainer"""
    data = []
    
    for text, labels in examples:
        data.append({
            'text': text,
            'labels': labels
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Training data saved to {output_path}")


def load_training_data(input_path: str) -> List[Tuple[str, List[str]]]:
    """Load training data from JSON file"""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    examples = []
    for item in data:
        text = item.get('text', '')
        labels = item.get('labels', [])
        examples.append((text, labels))
    
    return examples


def augment_with_rule_based(examples: List[Tuple[str, List[str]]], 
                           augment_ratio: float = 0.5) -> List[Tuple[str, List[str]]]:
    """Augment training data with rule-based examples"""
    
    # Sample patterns for augmentation
    test_patterns = [
        "Glucose {value} mg/dL {range}",
        "Hemoglobin {value} g/dL {range}",
        "Cholesterol Total {value} {flag} mg/dL {range}",
        "White Blood Cell Count {value} K/uL {range}",
        "Creatinine {value} mg/dL {range}",
        "Sodium {value} mEq/L {range}",
        "Potassium {value} {flag} mEq/L {range}",
    ]
    
    values = ["95", "12.5", "180", "7.2", "1.8", "140", "4.5"]
    flags = ["*", "H", "L", "HIGH", "LOW", ""]
    ranges = ["70-100", "<200", "4.0-11.0", "12-16", "0.7-1.3", "135-145"]
    
    splitter = RuleBasedSplitter()
    augmented = list(examples)  # Copy original data
    
    import random
    random.seed(42)
    
    num_to_generate = int(len(examples) * augment_ratio)
    
    for _ in range(num_to_generate):
        pattern = random.choice(test_patterns)
        value = random.choice(values)
        flag = random.choice(flags) if "{flag}" in pattern else ""
        range_val = random.choice(ranges)
        
        # Generate synthetic example
        synthetic_text = pattern.format(value=value, flag=flag, range=range_val).strip()
        # Clean up extra spaces
        synthetic_text = ' '.join(synthetic_text.split())
        
        # Get rule-based labels
        synthetic_labels = splitter.parse_to_bio_labels(synthetic_text)
        
        augmented.append((synthetic_text, synthetic_labels))
    
    print(f"Augmented dataset: {len(examples)} -> {len(augmented)} examples")
    return augmented


def main():
    parser = argparse.ArgumentParser(description='Prepare TEST_ROW token classification data')
    parser.add_argument('export_file', help='Label Studio export JSON file')
    parser.add_argument('--output', '-o', default='/data/training/testrow_training_data.json',
                       help='Output training data file')
    parser.add_argument('--augment', action='store_true',
                       help='Augment with rule-based synthetic examples')
    parser.add_argument('--validate', action='store_true',
                       help='Validate data without saving')
    
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
    
    # Extract all examples
    all_examples = []
    for i, task in enumerate(tasks):
        examples = extract_token_annotations(task)
        all_examples.extend(examples)
        print(f"Task {i+1}: extracted {len(examples)} examples")
    
    print(f"Total extracted examples: {len(all_examples)}")
    
    if not all_examples:
        print("Error: No examples extracted from export file")
        sys.exit(1)
    
    # Augment with synthetic data if requested
    if args.augment:
        print("Augmenting with rule-based synthetic examples...")
        all_examples = augment_with_rule_based(all_examples)
    
    # Validate data
    stats = validate_training_data(all_examples)
    
    print("\n=== Training Data Statistics ===")
    print(f"Total examples: {stats['total_examples']}")
    print(f"Total tokens: {stats['total_tokens']}")
    print(f"Average tokens per example: {stats['avg_tokens_per_example']:.1f}")
    
    print(f"\nLabel distribution:")
    for label, info in stats['label_distribution'].items():
        print(f"  {label}: {info['count']} ({info['percentage']:.1f}%)")
    
    print(f"\nEntity distribution:")
    for entity_type, info in stats['entity_distribution'].items():
        print(f"  {entity_type}: {info['entities']} entities, {info['tokens']} tokens")
    
    print(f"\nExample length distribution:")
    for length_range, count in sorted(stats['examples_by_length'].items()):
        print(f"  {length_range} tokens: {count} examples")
    
    if stats['validation_errors']:
        print(f"\n⚠️  Validation errors ({len(stats['validation_errors'])}):")
        for error in stats['validation_errors'][:10]:
            print(f"  - {error}")
        if len(stats['validation_errors']) > 10:
            print(f"  ... and {len(stats['validation_errors']) - 10} more")
    
    # Check for class imbalance
    label_counts = [info['count'] for info in stats['label_distribution'].values()]
    if label_counts:
        o_count = stats['label_distribution'].get('O', {}).get('count', 0)
        non_o_count = sum(label_counts) - o_count
        
        if o_count > 0 and non_o_count > 0:
            imbalance_ratio = o_count / non_o_count
            print(f"\nClass imbalance (O vs non-O): {imbalance_ratio:.2f}")
            
            if imbalance_ratio > 5:
                print("⚠️  High class imbalance detected!")
                print("Consider using class weights or data balancing techniques")
    
    if args.validate:
        print("\nValidation complete. Exiting without saving.")
        sys.exit(0)
    
    # Save training data
    save_training_data(all_examples, args.output)
    
    print(f"\n✅ Data preparation complete!")
    print(f"Next steps:")
    print(f"  1. Review the statistics above")
    print(f"  2. Train model: python train_testrow.py {args.output}")
    print(f"  3. Evaluate: python eval_testrow.py")


if __name__ == '__main__':
    main()