#!/usr/bin/env python3
"""
Convert Label Studio role annotations to CSV format for training

Converts exported Label Studio JSON annotations to the CSV format
expected by the roles trainer in services/trainer/roles/
"""

import argparse
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd


def convert_ls_export_to_csv(ls_export_file: Path, output_csv: Path) -> None:
    """
    Convert Label Studio export JSON to roles training CSV format
    
    Args:
        ls_export_file: Path to Label Studio JSON export
        output_csv: Path for output CSV file
    """
    print(f"📖 Reading Label Studio export: {ls_export_file}")
    
    with open(ls_export_file, 'r', encoding='utf-8') as f:
        ls_data = json.load(f)
    
    print(f"📊 Found {len(ls_data)} labeled items")
    
    # Convert to training format
    training_rows = []
    stats = {
        'total_items': len(ls_data),
        'labeled_items': 0,
        'skipped_items': 0,
        'role_counts': {}
    }
    
    for item in ls_data:
        # Extract data fields
        data = item.get('data', {})
        text = data.get('text', '').strip()
        page = data.get('page', 1)
        y_tertile = data.get('y_tertile', 1)
        is_bold = data.get('is_bold', False)
        source_file = data.get('source_file', 'unknown')
        
        # Extract annotations
        annotations = item.get('annotations', [])
        if not annotations:
            stats['skipped_items'] += 1
            continue
            
        # Get the most recent annotation (in case of multiple)
        annotation = annotations[-1]  # Latest annotation
        results = annotation.get('result', [])
        
        # Find role classification result
        role = None
        for result in results:
            if result.get('from_name') == 'role' and 'choices' in result.get('value', {}):
                choices = result['value']['choices']
                if choices:
                    role = choices[0]  # Single choice selection
                    break
        
        if not role:
            stats['skipped_items'] += 1
            continue
        
        # Build training row
        training_row = {
            'text': text,
            'y_tertile': int(y_tertile),
            'is_bold': bool(is_bold),
            'is_header_hint': False,  # Default - could be enhanced
            'role': role,
            'page': int(page),
            'source_file': source_file
        }
        
        training_rows.append(training_row)
        stats['labeled_items'] += 1
        stats['role_counts'][role] = stats['role_counts'].get(role, 0) + 1
    
    # Write CSV
    print(f"📝 Writing {len(training_rows)} training rows to: {output_csv}")
    
    fieldnames = ['text', 'y_tertile', 'is_bold', 'is_header_hint', 'role', 'page', 'source_file']
    
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(training_rows)
    
    # Print statistics
    print("\n📊 Conversion Statistics:")
    print(f"  Total items: {stats['total_items']}")
    print(f"  Labeled items: {stats['labeled_items']}")
    print(f"  Skipped items: {stats['skipped_items']}")
    print(f"  Success rate: {stats['labeled_items']/stats['total_items']*100:.1f}%")
    
    print("\n🏷️  Role Distribution:")
    for role, count in sorted(stats['role_counts'].items()):
        print(f"  {role}: {count} ({count/stats['labeled_items']*100:.1f}%)")
    
    # Quality checks
    print("\n✅ Quality Checks:")
    
    # Check for role balance
    role_counts = list(stats['role_counts'].values())
    if role_counts:
        min_count = min(role_counts)
        max_count = max(role_counts)
        imbalance_ratio = max_count / min_count if min_count > 0 else float('inf')
        
        if imbalance_ratio > 10:
            print(f"  ⚠️  High class imbalance (ratio: {imbalance_ratio:.1f})")
        else:
            print(f"  ✅ Reasonable class balance (ratio: {imbalance_ratio:.1f})")
    
    # Check for minimum sample sizes
    min_samples = 5
    under_represented = [role for role, count in stats['role_counts'].items() 
                        if count < min_samples]
    
    if under_represented:
        print(f"  ⚠️  Roles with <{min_samples} samples: {under_represented}")
        print(f"      Consider labeling more examples of these roles")
    else:
        print(f"  ✅ All roles have ≥{min_samples} samples")
    
    # Check for TEST_ROW coverage (most important)
    test_row_count = stats['role_counts'].get('TEST_ROW', 0)
    if test_row_count < 20:
        print(f"  ⚠️  Only {test_row_count} TEST_ROW samples (recommend ≥20)")
    else:
        print(f"  ✅ Good TEST_ROW coverage: {test_row_count} samples")


def merge_with_existing_data(new_csv: Path, existing_csv: Path, output_csv: Path) -> None:
    """
    Merge new labeled data with existing training data
    
    Args:
        new_csv: New labeled data from Label Studio
        existing_csv: Existing training CSV
        output_csv: Combined output CSV
    """
    print(f"🔄 Merging labeled data...")
    print(f"  New data: {new_csv}")
    print(f"  Existing: {existing_csv}")
    print(f"  Output: {output_csv}")
    
    # Read both files
    new_df = pd.read_csv(new_csv)
    existing_df = pd.read_csv(existing_csv) if existing_csv.exists() else pd.DataFrame()
    
    print(f"📊 New data: {len(new_df)} rows")
    print(f"📊 Existing data: {len(existing_df)} rows")
    
    if not existing_df.empty:
        # Remove duplicates (same text)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        before_dedup = len(combined_df)
        combined_df = combined_df.drop_duplicates(subset=['text'], keep='last')
        after_dedup = len(combined_df)
        
        if before_dedup > after_dedup:
            print(f"🔍 Removed {before_dedup - after_dedup} duplicate texts")
    else:
        combined_df = new_df
    
    # Write merged data
    combined_df.to_csv(output_csv, index=False)
    print(f"✅ Merged dataset: {len(combined_df)} total rows")
    
    # Show final role distribution
    print("\n🏷️  Final Role Distribution:")
    role_counts = combined_df['role'].value_counts()
    for role, count in role_counts.items():
        print(f"  {role}: {count}")


def validate_csv_format(csv_file: Path) -> bool:
    """Validate that CSV has expected format for roles trainer"""
    
    expected_columns = {'text', 'y_tertile', 'is_bold', 'is_header_hint', 'role'}
    
    try:
        df = pd.read_csv(csv_file)
        actual_columns = set(df.columns)
        
        print(f"🔍 Validating CSV format: {csv_file}")
        print(f"  Expected columns: {expected_columns}")
        print(f"  Actual columns: {actual_columns}")
        
        missing = expected_columns - actual_columns
        extra = actual_columns - expected_columns
        
        if missing:
            print(f"  ❌ Missing columns: {missing}")
            return False
        
        if extra:
            print(f"  ℹ️  Extra columns: {extra}")
        
        # Check data types
        print(f"  📊 Total rows: {len(df)}")
        print(f"  🏷️  Unique roles: {df['role'].nunique()}")
        
        role_counts = df['role'].value_counts()
        print("  📋 Role counts:")
        for role, count in role_counts.items():
            print(f"    {role}: {count}")
        
        print("  ✅ CSV format is valid!")
        return True
        
    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Convert Label Studio role annotations to training CSV format"
    )
    parser.add_argument(
        "ls_export", 
        type=Path,
        help="Path to Label Studio JSON export file"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output CSV file (default: same dir as input)"
    )
    parser.add_argument(
        "--merge-with",
        type=Path,
        help="Existing CSV to merge with (combines old + new data)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate an existing CSV file"
    )
    
    args = parser.parse_args()
    
    # Validate mode
    if args.validate_only:
        validate_csv_format(args.ls_export)
        return
    
    # Check input file
    if not args.ls_export.exists():
        print(f"❌ Input file not found: {args.ls_export}")
        return
    
    # Determine output file
    if args.output:
        output_csv = args.output
    else:
        output_csv = args.ls_export.parent / f"{args.ls_export.stem}_roles.csv"
    
    # Convert Label Studio export to CSV
    convert_ls_export_to_csv(args.ls_export, output_csv)
    
    # Merge with existing data if requested
    if args.merge_with:
        if args.merge_with.exists():
            merged_output = args.ls_export.parent / f"{args.ls_export.stem}_merged.csv"
            merge_with_existing_data(output_csv, args.merge_with, merged_output)
            print(f"\n🔗 Merged data written to: {merged_output}")
        else:
            print(f"⚠️  Existing file not found: {args.merge_with}")
    
    # Validate output
    print("\n" + "="*50)
    validate_csv_format(output_csv)
    
    print(f"\n✅ Conversion complete! Output: {output_csv}")
    print("\n💡 Next steps:")
    print("1. Review the role distribution and balance")
    print("2. Add more labels for under-represented roles if needed")  
    print("3. Use this CSV with services/trainer/roles/train_roles.py")
    print("4. Evaluate model performance on held-out test data")


if __name__ == "__main__":
    main()