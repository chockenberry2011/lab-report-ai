#!/usr/bin/env python3
"""
Convert Label Studio test-row annotations to NER format for training

Converts Label Studio NER/entity annotations to the BIO format
expected by the test-row token classifier in services/trainer/testrow/
"""

import argparse
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
import re


# Token labels for TEST_ROW NER (from token_classifier.py)
TOKEN_LABELS = [
    'O',           # Outside/Other
    'B-TEST_NAME', # Beginning of test name
    'I-TEST_NAME', # Inside test name
    'B-VALUE',     # Beginning of value
    'I-VALUE',     # Inside value
    'B-UNIT',      # Beginning of unit
    'I-UNIT',      # Inside unit
    'B-REF_RANGE', # Beginning of reference range
    'I-REF_RANGE', # Inside reference range
    'B-FLAG',      # Beginning of flag
    'I-FLAG',      # Inside flag
    'B-COMMENT',   # Beginning of comment/note
    'I-COMMENT'    # Inside comment/note
]

# Entity mapping (Label Studio -> NER labels)
ENTITY_MAPPING = {
    'test_name': 'TEST_NAME',
    'value': 'VALUE',
    'unit': 'UNIT',
    'ref_range': 'REF_RANGE',
    'reference_range': 'REF_RANGE',
    'flag': 'FLAG',
    'abnormal': 'FLAG',
    'critical': 'FLAG',
    'comment': 'COMMENT',
    'note': 'COMMENT',
    'remarks': 'COMMENT',
    'notes': 'COMMENT'
}


def create_testrow_labeling_config() -> str:
    """Generate Label Studio config for test-row NER labeling"""
    return """
<View>
  <Header value="Test Row NER Annotation"/>
  
  <Text name="test_line" value="$text" granularity="word"/>
  
  <Header value="Instructions"/>
  <Text value="Select and label the components in this test result line:"/>
  
  <Labels name="entities" toName="test_line">
    <Label value="test_name" background="#FF6B6B" hint="Test/analyte name"/>
    <Label value="value" background="#4ECDC4" hint="Numeric result value"/>
    <Label value="unit" background="#45B7D1" hint="Unit of measurement"/>
    <Label value="ref_range" background="#96CEB4" hint="Reference range"/>
    <Label value="flag" background="#FECA57" hint="Abnormal/critical flags"/>
    <Label value="comment" background="#DDA0DD" hint="Test comments/notes"/>
  </Labels>
  
  <Header value="Example Annotations"/>
  <Text value="Glucose    95    mg/dL    70-100"/>
  <Text value="↑ test_name ↑ value ↑ unit ↑ ref_range"/>
  
</View>
""".strip()


def tokenize_text(text: str) -> List[str]:
    """Simple whitespace tokenization for test lines"""
    # Split on whitespace but preserve structure
    tokens = text.split()
    
    # Further split tokens that contain punctuation
    refined_tokens = []
    for token in tokens:
        # Split on common separators but keep them
        parts = re.split(r'(\W+)', token)
        refined_tokens.extend([p for p in parts if p.strip()])
    
    return refined_tokens


def align_entities_to_tokens(text: str, entities: List[Dict], tokens: List[str]) -> List[str]:
    """
    Align entity spans to tokenized text and create BIO labels
    
    Args:
        text: Original text
        entities: List of entity dicts with 'start', 'end', 'text', 'labels'
        tokens: Tokenized text
        
    Returns:
        List of BIO labels for each token
    """
    # Initialize all tokens as 'O'
    labels = ['O'] * len(tokens)
    
    # Create character to token mapping
    char_to_token = {}
    current_pos = 0
    
    for i, token in enumerate(tokens):
        # Find token position in original text
        token_start = text.find(token, current_pos)
        if token_start == -1:
            continue  # Skip if token not found
            
        token_end = token_start + len(token)
        
        # Map all characters in this token to token index
        for char_idx in range(token_start, token_end):
            char_to_token[char_idx] = i
            
        current_pos = token_end
    
    # Process entities and assign BIO labels
    for entity in entities:
        start_char = entity['start']
        end_char = entity['end']
        entity_text = entity['text']
        entity_labels = entity.get('labels', [])
        
        if not entity_labels:
            continue
            
        # Map entity type
        entity_label = entity_labels[0].lower()
        ner_label = ENTITY_MAPPING.get(entity_label, 'O')
        
        if ner_label == 'O':
            continue
        
        # Find tokens that overlap with entity
        entity_tokens = []
        for char_idx in range(start_char, end_char):
            if char_idx in char_to_token:
                token_idx = char_to_token[char_idx]
                if token_idx not in entity_tokens:
                    entity_tokens.append(token_idx)
        
        # Assign BIO labels
        if entity_tokens:
            # First token gets B- label
            labels[entity_tokens[0]] = f'B-{ner_label}'
            
            # Subsequent tokens get I- labels
            for token_idx in entity_tokens[1:]:
                labels[token_idx] = f'I-{ner_label}'
    
    return labels


def convert_ls_export_to_ner(ls_export_file: Path, output_jsonl: Path) -> None:
    """
    Convert Label Studio export JSON to NER training format
    
    Args:
        ls_export_file: Path to Label Studio JSON export
        output_jsonl: Path for output JSONL file (one example per line)
    """
    print(f"📖 Reading Label Studio export: {ls_export_file}")
    
    with open(ls_export_file, 'r', encoding='utf-8') as f:
        ls_data = json.load(f)
    
    print(f"📊 Found {len(ls_data)} labeled items")
    
    # Convert to NER format
    ner_examples = []
    stats = {
        'total_items': len(ls_data),
        'labeled_items': 0,
        'skipped_items': 0,
        'entity_counts': {},
        'token_counts': {}
    }
    
    for item in ls_data:
        # Extract data
        data = item.get('data', {})
        text = data.get('text', '').strip()
        
        if not text:
            stats['skipped_items'] += 1
            continue
        
        # Extract annotations
        annotations = item.get('annotations', [])
        if not annotations:
            stats['skipped_items'] += 1
            continue
        
        # Get the most recent annotation
        annotation = annotations[-1]
        results = annotation.get('result', [])
        
        # Extract entity annotations
        entities = []
        for result in results:
            if result.get('from_name') == 'entities' and result.get('type') == 'labels':
                value = result.get('value', {})
                entities.append({
                    'start': value.get('start', 0),
                    'end': value.get('end', 0),
                    'text': value.get('text', ''),
                    'labels': value.get('labels', [])
                })
        
        # Tokenize text
        tokens = tokenize_text(text)
        
        # Align entities to tokens
        labels = align_entities_to_tokens(text, entities, tokens)
        
        # Create NER example
        ner_example = {
            'text': text,
            'tokens': tokens,
            'labels': labels,
            'source_file': data.get('source_file', 'unknown'),
            'entities': entities  # Keep original entities for debugging
        }
        
        ner_examples.append(ner_example)
        stats['labeled_items'] += 1
        
        # Update statistics
        for label in labels:
            stats['token_counts'][label] = stats['token_counts'].get(label, 0) + 1
        
        for entity in entities:
            entity_type = entity.get('labels', ['unknown'])[0]
            stats['entity_counts'][entity_type] = stats['entity_counts'].get(entity_type, 0) + 1
    
    # Write JSONL output
    print(f"📝 Writing {len(ner_examples)} NER examples to: {output_jsonl}")
    
    with open(output_jsonl, 'w', encoding='utf-8') as f:
        for example in ner_examples:
            json.dump(example, f, ensure_ascii=False)
            f.write('\n')
    
    # Print statistics
    print("\n📊 Conversion Statistics:")
    print(f"  Total items: {stats['total_items']}")
    print(f"  Labeled items: {stats['labeled_items']}")
    print(f"  Skipped items: {stats['skipped_items']}")
    print(f"  Success rate: {stats['labeled_items']/stats['total_items']*100:.1f}%")
    
    print("\n🏷️  Entity Distribution:")
    for entity_type, count in sorted(stats['entity_counts'].items()):
        print(f"  {entity_type}: {count} entities")
    
    print("\n🎯 Token Label Distribution:")
    total_tokens = sum(stats['token_counts'].values())
    for label, count in sorted(stats['token_counts'].items()):
        pct = count / total_tokens * 100 if total_tokens > 0 else 0
        print(f"  {label}: {count} ({pct:.1f}%)")
    
    # Quality checks
    print("\n✅ Quality Checks:")
    
    # Check for label coverage
    bio_labels = [label for label in stats['token_counts'].keys() if label != 'O']
    missing_labels = set(TOKEN_LABELS) - set(['O']) - set(bio_labels)
    
    if missing_labels:
        print(f"  ⚠️  Missing labels: {missing_labels}")
        print(f"      Consider labeling examples with these entity types")
    else:
        print(f"  ✅ All entity types represented")
    
    # Check O vs entity ratio
    o_count = stats['token_counts'].get('O', 0)
    entity_count = total_tokens - o_count
    o_ratio = o_count / total_tokens if total_tokens > 0 else 0
    
    if o_ratio > 0.8:
        print(f"  ⚠️  High O ratio: {o_ratio:.1f} (consider more dense entity annotations)")
    elif o_ratio < 0.3:
        print(f"  ⚠️  Low O ratio: {o_ratio:.1f} (check for over-annotation)")
    else:
        print(f"  ✅ Good O/entity balance: {o_ratio:.1f}")
    
    # Check for critical entities
    critical_entities = ['value', 'test_name']
    for entity in critical_entities:
        count = stats['entity_counts'].get(entity, 0)
        if count < 10:
            print(f"  ⚠️  Low {entity} count: {count} (recommend ≥10)")
        else:
            print(f"  ✅ Good {entity} coverage: {count} examples")


def convert_to_csv_format(jsonl_file: Path, output_csv: Path) -> None:
    """
    Convert JSONL NER format to CSV for easier inspection
    
    Args:
        jsonl_file: Input JSONL file
        output_csv: Output CSV file
    """
    print(f"📄 Converting JSONL to CSV format: {jsonl_file} -> {output_csv}")
    
    rows = []
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            example = json.loads(line)
            text = example['text']
            tokens = example['tokens']
            labels = example['labels']
            
            for i, (token, label) in enumerate(zip(tokens, labels)):
                rows.append({
                    'text_id': hash(text) % 100000,  # Simple text ID
                    'token_index': i,
                    'token': token,
                    'label': label,
                    'full_text': text
                })
    
    # Write CSV
    df = pd.DataFrame(rows)
    df.to_csv(output_csv, index=False)
    
    print(f"✅ Converted to CSV: {len(rows)} token rows")


def validate_ner_format(jsonl_file: Path) -> bool:
    """Validate NER JSONL format"""
    
    try:
        print(f"🔍 Validating NER format: {jsonl_file}")
        
        examples = []
        with open(jsonl_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                try:
                    example = json.loads(line)
                    examples.append(example)
                except json.JSONDecodeError as e:
                    print(f"  ❌ JSON error on line {line_num}: {e}")
                    return False
        
        print(f"  📊 Total examples: {len(examples)}")
        
        # Validate format
        required_keys = {'text', 'tokens', 'labels'}
        for i, example in enumerate(examples):
            missing_keys = required_keys - set(example.keys())
            if missing_keys:
                print(f"  ❌ Example {i} missing keys: {missing_keys}")
                return False
            
            # Check token/label alignment
            if len(example['tokens']) != len(example['labels']):
                print(f"  ❌ Example {i}: token/label length mismatch")
                print(f"      Tokens: {len(example['tokens'])}, Labels: {len(example['labels'])}")
                return False
        
        # Check label validity
        all_labels = set()
        for example in examples:
            all_labels.update(example['labels'])
        
        invalid_labels = all_labels - set(TOKEN_LABELS)
        if invalid_labels:
            print(f"  ❌ Invalid labels found: {invalid_labels}")
            print(f"      Valid labels: {TOKEN_LABELS}")
            return False
        
        print(f"  🏷️  Labels used: {sorted(all_labels)}")
        print("  ✅ NER format is valid!")
        return True
        
    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert Label Studio test-row annotations to NER format"
    )
    parser.add_argument(
        "ls_export", 
        type=Path,
        help="Path to Label Studio JSON export file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output JSONL file (default: same dir as input)"
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also create CSV format for inspection"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate an existing JSONL file"
    )
    parser.add_argument(
        "--print-config",
        action="store_true", 
        help="Print Label Studio configuration for test-row NER"
    )
    
    args = parser.parse_args()
    
    # Print configuration
    if args.print_config:
        print("Label Studio Configuration for Test-Row NER:")
        print("=" * 50)
        print(create_testrow_labeling_config())
        print("=" * 50)
        return
    
    # Validate mode
    if args.validate_only:
        validate_ner_format(args.ls_export)
        return
    
    # Check input file
    if not args.ls_export.exists():
        print(f"❌ Input file not found: {args.ls_export}")
        return
    
    # Determine output file
    if args.output:
        output_jsonl = args.output
    else:
        output_jsonl = args.ls_export.parent / f"{args.ls_export.stem}_ner.jsonl"
    
    # Convert Label Studio export to NER format
    convert_ls_export_to_ner(args.ls_export, output_jsonl)
    
    # Create CSV version if requested
    if args.csv:
        csv_output = output_jsonl.parent / f"{output_jsonl.stem}.csv"
        convert_to_csv_format(output_jsonl, csv_output)
    
    # Validate output
    print("\n" + "="*50)
    validate_ner_format(output_jsonl)
    
    print(f"\n✅ Conversion complete! Output: {output_jsonl}")
    print("\n💡 Next steps:")
    print("1. Review the entity distribution and token balance")
    print("2. Add more annotations for under-represented entities")
    print("3. Use this JSONL with services/trainer/testrow/train_testrow.py")
    print("4. Evaluate model performance on held-out test data")
    
    print("\n🏷️  Label Studio Setup Tips:")
    print("- Use --print-config to get the NER labeling configuration")
    print("- Focus on TEST_NAME, VALUE, UNIT, REF_RANGE entities")
    print("- Label 50-100 diverse test lines for good coverage")
    print("- Include various formats: 'Glucose 95 mg/dL 70-100'")


if __name__ == "__main__":
    main()