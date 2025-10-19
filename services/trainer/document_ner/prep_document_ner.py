#!/usr/bin/env python3
"""
Prepare document-level NER training data from Label Studio export.

Converts Label Studio NER annotations for full documents into training format
for the comprehensive document NER model.
"""

import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import re

try:
    from .entity_labels import DOCUMENT_ENTITY_LABELS, get_entity_type, ENTITY_CATEGORIES
    from .document_classifier import DocumentNERClassifier
except ImportError:
    from entity_labels import DOCUMENT_ENTITY_LABELS, get_entity_type, ENTITY_CATEGORIES
    from document_classifier import DocumentNERClassifier


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


def tokenize_document(text: str) -> List[str]:
    """
    Tokenize document text for NER.

    Uses whitespace + punctuation splitting that preserves important
    patterns for entity recognition.
    """
    # Split on whitespace and common punctuation, but preserve structure
    # This is a simple tokenizer - could be enhanced with spaCy or similar

    # First, normalize some whitespace
    text = re.sub(r'\s+', ' ', text.strip())

    # Split on whitespace
    tokens = []
    for chunk in text.split():
        # Further split on punctuation, but keep punctuation as separate tokens
        # when it's meaningful (like colons in "Patient: John Doe")

        # Handle special punctuation
        chunk = re.sub(r'([,:;(){}])', r' \1 ', chunk)
        chunk = re.sub(r'\s+', ' ', chunk)

        for token in chunk.split():
            if token.strip():
                tokens.append(token.strip())

    return tokens


def align_labels_to_tokens(text: str, tokens: List[str], annotations: List[Dict[str, Any]]) -> List[str]:
    """
    Align Label Studio span annotations to tokenized text.

    This is the tricky part - Label Studio gives character-level spans,
    but we need token-level BIO labels.
    """
    # Initialize all tokens as 'O'
    labels = ['O'] * len(tokens)

    # Sort annotations by start position
    annotations.sort(key=lambda x: x.get('start', 0))

    # Build token position mapping
    token_positions = []
    text_pos = 0

    for token in tokens:
        # Find token in text starting from current position
        start_pos = text.find(token, text_pos)
        if start_pos == -1:
            # Token not found - this is a tokenization issue
            # For now, use approximate position
            start_pos = text_pos
            end_pos = start_pos + len(token)
        else:
            end_pos = start_pos + len(token)
            text_pos = end_pos

        token_positions.append((start_pos, end_pos))

    # Apply annotations to tokens
    for annotation in annotations:
        start_char = annotation.get('start', 0)
        end_char = annotation.get('end', len(text))
        entity_type = annotation.get('labels', ['O'])[0]

        if entity_type not in [label[2:] for label in DOCUMENT_ENTITY_LABELS if label != 'O']:
            print(f"Warning: Unknown entity type '{entity_type}', skipping")
            continue

        # Find tokens that overlap with this annotation
        overlapping_tokens = []
        for i, (token_start, token_end) in enumerate(token_positions):
            # Check if token overlaps with annotation span
            if not (token_end <= start_char or token_start >= end_char):
                overlapping_tokens.append(i)

        # Apply BIO labels
        for i, token_idx in enumerate(overlapping_tokens):
            if i == 0:
                labels[token_idx] = f'B-{entity_type}'
            else:
                labels[token_idx] = f'I-{entity_type}'

    return labels


def extract_document_annotation(task: Dict[str, Any]) -> Optional[Tuple[List[str], List[str]]]:
    """Extract tokens and labels from a single Label Studio task"""

    # Get document text
    text = task.get('data', {}).get('text', '')
    if not text.strip():
        return None

    # Get annotations
    annotations_list = task.get('annotations', [])
    if not annotations_list:
        print(f"Warning: No annotations found in task {task.get('id', 'unknown')}")
        return None

    # Use the latest annotation
    annotation = annotations_list[-1]
    results = annotation.get('result', [])

    # Extract span annotations
    span_annotations = []
    for result in results:
        if result.get('type') == 'labels':  # NER span annotation
            value = result.get('value', {})
            span_annotations.append({
                'start': value.get('start', 0),
                'end': value.get('end', len(text)),
                'labels': value.get('labels', ['O'])
            })

    if not span_annotations:
        print(f"Warning: No span annotations found in task {task.get('id', 'unknown')}")
        return None

    # Tokenize the document
    tokens = tokenize_document(text)

    # Align annotations to tokens
    labels = align_labels_to_tokens(text, tokens, span_annotations)

    # Validate that we have same number of tokens and labels
    if len(tokens) != len(labels):
        print(f"Warning: Token/label mismatch in task {task.get('id', 'unknown')}: {len(tokens)} tokens, {len(labels)} labels")
        return None

    return tokens, labels


def validate_training_data(examples: List[Tuple[List[str], List[str]]]) -> Dict[str, Any]:
    """Validate and analyze training data"""
    stats = {
        'total_examples': len(examples),
        'total_tokens': 0,
        'label_distribution': {},
        'entity_distribution': {},
        'validation_errors': [],
        'avg_tokens_per_example': 0,
        'examples_by_length': {},
        'entity_coverage': {}
    }

    all_labels = []

    for i, (tokens, labels) in enumerate(examples):
        # Validate length match
        if len(tokens) != len(labels):
            stats['validation_errors'].append(
                f"Example {i}: Length mismatch - {len(tokens)} tokens, {len(labels)} labels"
            )
            continue

        # Count tokens and labels
        stats['total_tokens'] += len(labels)
        all_labels.extend(labels)

        # Track example length
        length_bin = len(tokens) // 50 * 50  # Group by 50s
        stats['examples_by_length'][f'{length_bin}-{length_bin+49}'] = \
            stats['examples_by_length'].get(f'{length_bin}-{length_bin+49}', 0) + 1

        # Validate individual labels
        for j, label in enumerate(labels):
            if label not in DOCUMENT_ENTITY_LABELS:
                stats['validation_errors'].append(
                    f"Example {i}, token {j}: Invalid label '{label}'"
                )

    # Calculate label distribution
    for label in DOCUMENT_ENTITY_LABELS:
        count = all_labels.count(label)
        stats['label_distribution'][label] = {
            'count': count,
            'percentage': (count / len(all_labels) * 100) if all_labels else 0
        }

    # Calculate entity distribution by category
    for category, entity_types in ENTITY_CATEGORIES.items():
        category_count = 0
        for entity_type in entity_types:
            b_count = all_labels.count(f'B-{entity_type}')
            category_count += b_count
        stats['entity_coverage'][category] = category_count

    # Calculate averages
    if examples:
        stats['avg_tokens_per_example'] = stats['total_tokens'] / len(examples)

    return stats


def save_training_data(examples: List[Tuple[List[str], List[str]]], output_path: str):
    """Save training data in JSONL format"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for tokens, labels in examples:
            example = {
                'tokens': tokens,
                'labels': labels
            }
            f.write(json.dumps(example, ensure_ascii=False) + '\n')

    print(f"Training data saved to {output_path}")


def load_training_data(input_path: str) -> List[Tuple[List[str], List[str]]]:
    """Load training data from JSONL file"""
    examples = []
    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            example = json.loads(line)
            tokens = example.get('tokens', [])
            labels = example.get('labels', [])
            examples.append((tokens, labels))

    return examples


def augment_with_synthetic_data(examples: List[Tuple[List[str], List[str]]],
                               augment_ratio: float = 0.2) -> List[Tuple[List[str], List[str]]]:
    """
    Augment training data with synthetic examples.

    Creates variations of common patterns to help model generalize.
    """
    # Synthetic patterns for common field variations
    patient_patterns = [
        ("Patient Name: {last}, {first}", ["O", "O", "B-PATIENT_LAST_NAME", "B-PATIENT_FIRST_NAME"]),
        ("Patient: {first} {last}", ["O", "B-PATIENT_FIRST_NAME", "B-PATIENT_LAST_NAME"]),
        ("{last}, {first}", ["B-PATIENT_LAST_NAME", "B-PATIENT_FIRST_NAME"]),
        ("Name: {first} {last}", ["O", "B-PATIENT_FIRST_NAME", "B-PATIENT_LAST_NAME"]),
        ("DOB: {date}", ["O", "B-PATIENT_DOB"]),
        ("Date of Birth: {date}", ["O", "O", "O", "B-PATIENT_DOB"]),
        ("Sex: {sex}", ["O", "B-PATIENT_SEX"]),
        ("Gender: {sex}", ["O", "B-PATIENT_SEX"]),
        ("MRN: {mrn}", ["O", "B-PATIENT_MRN"]),
        ("Patient ID: {mrn}", ["O", "O", "B-PATIENT_MRN"]),
    ]

    # Sample values
    first_names = ["JOHN", "JANE", "MICHAEL", "SARAH", "DAVID", "MARY"]
    last_names = ["DOE", "SMITH", "JOHNSON", "BROWN", "DAVIS", "WILSON"]
    dates = ["01/01/1960", "12/25/1975", "06/15/1980", "03/22/1965"]
    sexes = ["M", "F", "Male", "Female"]
    mrns = ["A123456", "12345678", "MRN123456", "P987654321"]

    augmented = list(examples)  # Copy original data

    import random
    random.seed(42)

    num_to_generate = int(len(examples) * augment_ratio)

    for _ in range(num_to_generate):
        pattern, label_template = random.choice(patient_patterns)

        # Fill in pattern
        synthetic_text = pattern.format(
            first=random.choice(first_names),
            last=random.choice(last_names),
            date=random.choice(dates),
            sex=random.choice(sexes),
            mrn=random.choice(mrns)
        )

        # Tokenize and create labels
        tokens = tokenize_document(synthetic_text)

        # This is simplified - in practice you'd need more sophisticated label alignment
        # For now, just use a simple approach
        if len(tokens) == len(label_template):
            labels = label_template
        else:
            # Fall back to simple labeling
            labels = ['O'] * len(tokens)

        augmented.append((tokens, labels))

    print(f"Augmented dataset: {len(examples)} -> {len(augmented)} examples")
    return augmented


def main():
    parser = argparse.ArgumentParser(description='Prepare document-level NER training data')
    parser.add_argument('export_file', help='Label Studio export JSON file')
    parser.add_argument('--output', '-o', default='/data/training/document_ner/training_data.jsonl',
                       help='Output training data file')
    parser.add_argument('--augment', action='store_true',
                       help='Augment with synthetic examples')
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
        example = extract_document_annotation(task)
        if example:
            all_examples.append(example)
            tokens, labels = example
            print(f"Task {i+1}: extracted {len(tokens)} tokens")
        else:
            print(f"Task {i+1}: failed to extract")

    print(f"Total extracted examples: {len(all_examples)}")

    if not all_examples:
        print("Error: No examples extracted from export file")
        sys.exit(1)

    # Augment with synthetic data if requested
    if args.augment:
        print("Augmenting with synthetic examples...")
        all_examples = augment_with_synthetic_data(all_examples)

    # Validate data
    stats = validate_training_data(all_examples)

    print("\n=== Training Data Statistics ===")
    print(f"Total examples: {stats['total_examples']}")
    print(f"Total tokens: {stats['total_tokens']}")
    print(f"Average tokens per example: {stats['avg_tokens_per_example']:.1f}")

    print(f"\nEntity coverage by category:")
    for category, count in stats['entity_coverage'].items():
        print(f"  {category}: {count} entities")

    print(f"\nTop label distribution:")
    sorted_labels = sorted(stats['label_distribution'].items(),
                          key=lambda x: x[1]['count'], reverse=True)
    for label, info in sorted_labels[:15]:  # Show top 15
        if info['count'] > 0:
            print(f"  {label}: {info['count']} ({info['percentage']:.1f}%)")

    print(f"\nExample length distribution:")
    for length_range, count in sorted(stats['examples_by_length'].items()):
        print(f"  {length_range} tokens: {count} examples")

    if stats['validation_errors']:
        print(f"\n⚠️  Validation errors ({len(stats['validation_errors'])}):")
        for error in stats['validation_errors'][:10]:
            print(f"  - {error}")
        if len(stats['validation_errors']) > 10:
            print(f"  ... and {len(stats['validation_errors']) - 10} more")

    # Check coverage
    entity_counts = list(stats['entity_coverage'].values())
    if entity_counts:
        min_coverage = min(entity_counts)
        if min_coverage == 0:
            print(f"\n⚠️  Some entity categories have no examples!")
            print("Consider adding more diverse training data.")

    if args.validate:
        print("\nValidation complete. Exiting without saving.")
        sys.exit(0)

    # Save training data
    save_training_data(all_examples, args.output)

    print(f"\n✅ Data preparation complete!")
    print(f"Next steps:")
    print(f"  1. Review the statistics above")
    print(f"  2. Split data: python -m services.trainer.document_ner.split_data {args.output}")
    print(f"  3. Train model: python -m services.trainer.document_ner.train_document_ner")


if __name__ == '__main__':
    main()