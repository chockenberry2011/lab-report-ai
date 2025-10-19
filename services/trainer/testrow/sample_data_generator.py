#!/usr/bin/env python3
"""
Generate synthetic TEST_ROW data for training and testing

Creates realistic medical test result lines with proper BIO labels.
"""

import json
import random
import argparse
from pathlib import Path
from typing import List, Tuple, Dict

try:
    from .rule_splitter import RuleBasedSplitter
except ImportError:  # fallback when run as a plain script
    from rule_splitter import RuleBasedSplitter


class TestRowSampleGenerator:
    """Generate synthetic TEST_ROW examples with BIO labels"""
    
    def __init__(self, random_seed: int = 42):
        random.seed(random_seed)
        self.splitter = RuleBasedSplitter()
        
        # Define component vocabularies
        self.test_names = [
            "Glucose", "Hemoglobin", "Hemoglobin A1c", "White Blood Cell Count",
            "Red Blood Cell Count", "Platelet Count", "Hematocrit", 
            "Total Cholesterol", "HDL Cholesterol", "LDL Cholesterol", "Triglycerides",
            "Creatinine", "Blood Urea Nitrogen", "Sodium", "Potassium", "Chloride",
            "CO2", "Albumin", "Total Protein", "ALT", "AST", "Alkaline Phosphatase",
            "Total Bilirubin", "Direct Bilirubin", "Thyroid Stimulating Hormone",
            "Free T4", "Vitamin D", "Vitamin B12", "Folate", "Iron", "TIBC",
            "Ferritin", "C-Reactive Protein", "Sed Rate", "Prothrombin Time",
            "Partial Thromboplastin Time", "INR"
        ]
        
        self.complex_test_names = [
            "Comprehensive Metabolic Panel", "Basic Metabolic Panel", 
            "Lipid Panel", "Liver Function Panel", "Thyroid Function Tests",
            "Complete Blood Count", "Iron Studies", "Hepatitis Panel",
            "Cardiac Enzymes", "Tumor Markers", "Coagulation Studies"
        ]
        
        self.values = [
            "95", "12.5", "180", "7.2", "1.8", "140", "4.5", "25", "0.8", "2.1",
            "85", "15.2", "220", "8.1", "2.5", "138", "3.9", "45", "1.2", "3.8",
            "105", "11.8", "165", "6.8", "1.1", "142", "4.2", "38", "0.9", "2.4",
            "78", "13.7", "195", "7.9", "2.0", "136", "5.1", "52", "1.5", "4.2"
        ]
        
        self.qualitative_values = [
            "NEGATIVE", "POSITIVE", "NOT DETECTED", "DETECTED", 
            "NORMAL", "ABNORMAL", "REACTIVE", "NON-REACTIVE"
        ]
        
        self.units = [
            "mg/dL", "g/dL", "mmol/L", "mEq/L", "U/L", "IU/L", "ng/mL", "pg/mL",
            "μg/dL", "mcg/dL", "K/uL", "M/uL", "cells/uL", "/uL", "%", "ratio",
            "mIU/L", "ng/dL", "μg/mL", "units/mL", "mm/hr"
        ]
        
        self.reference_ranges = [
            "70-100", "12-16", "4.0-11.0", "135-145", "3.5-5.0", "98-107",
            "22-26", "3.5-5.0", "6.0-8.0", "7-56", "8-40", "44-147",
            "0.3-1.2", "0.0-0.3", "0.4-4.0", "0.8-1.8", "30-100", 
            "200-900", "2.5-15", "10-35", "<200", ">200", "NEGATIVE"
        ]
        
        self.flags = [
            "*", "**", "H", "L", "HIGH", "LOW", "CRITICAL", "PANIC", 
            "ABNORMAL", "ABN", "!", "!!"
        ]
    
    def generate_simple_test_row(self) -> Tuple[str, List[str]]:
        """Generate a simple test row: NAME VALUE UNIT RANGE"""
        test_name = random.choice(self.test_names)
        value = random.choice(self.values)
        unit = random.choice(self.units)
        ref_range = random.choice(self.reference_ranges)
        
        # Occasional flag
        flag = random.choice(self.flags) if random.random() < 0.3 else ""
        
        # Build text with spacing variations
        parts = [test_name]
        
        # Add padding spaces (realistic lab formatting)
        padding = " " * random.randint(1, 20)
        parts.append(padding + value)
        
        if flag:
            parts.append(" " + flag)
        
        parts.append(" " * random.randint(1, 8) + unit)
        parts.append(" " * random.randint(1, 12) + ref_range)
        
        text = "".join(parts)
        
        # Use rule-based splitter to get initial labels
        labels = self.splitter.parse_to_bio_labels(text)
        
        return text, labels
    
    def generate_complex_test_row(self) -> Tuple[str, List[str]]:
        """Generate a complex test row with multiple components"""
        patterns = [
            # Pattern 1: Long test name with qualitative result
            "{test_name} {value} {range}",
            
            # Pattern 2: Test with multiple flags
            "{test_name} {value} {flag1} {flag2} {unit} {range}",
            
            # Pattern 3: Test with comment-like structure
            "{test_name} {value} {unit} ({range}) {flag}",
            
            # Pattern 4: Abbreviated format
            "{abbrev} {value} {flag} {unit} Ref: {range}",
            
            # Pattern 5: Panel-style format
            "{test_name}: {value} {unit} [{range}]"
        ]
        
        pattern = random.choice(patterns)
        
        # Select components
        if "{abbrev}" in pattern:
            test_name = random.choice(self.test_names).split()[0]  # First word only
        else:
            test_name = random.choice(self.test_names + self.complex_test_names)
        
        if random.random() < 0.3:  # 30% chance of qualitative
            value = random.choice(self.qualitative_values)
        else:
            value = random.choice(self.values)
        
        unit = random.choice(self.units)
        ref_range = random.choice(self.reference_ranges)
        flag1 = random.choice(self.flags[:4])  # Simple flags
        flag2 = random.choice(self.flags[:4])
        flag = random.choice(self.flags)
        
        # Format the text
        text = pattern.format(
            test_name=test_name,
            abbrev=test_name,
            value=value,
            unit=unit,
            range=ref_range,
            flag1=flag1,
            flag2=flag2,
            flag=flag
        )
        
        # Clean up extra spaces
        text = ' '.join(text.split())
        
        # Get rule-based labels
        labels = self.splitter.parse_to_bio_labels(text)
        
        return text, labels
    
    def generate_edge_case(self) -> Tuple[str, List[str]]:
        """Generate edge cases and challenging examples"""
        edge_cases = [
            # Very long test names
            "Thyroid Stimulating Hormone Receptor Antibody {value} IU/L <1.75",
            
            # Multiple values (ranges)
            "Glucose Random {value1}-{value2} mg/dL 70-100",
            
            # Special characters
            "Hemoglobin A1c {value}% <7.0 *",
            
            # Mixed case and punctuation  
            "C-Reactive Protein, High Sensitivity {value} mg/L <3.0",
            
            # Qualitative with ranges
            "Hepatitis B Surface Antigen NEGATIVE - NEGATIVE",
            
            # Multiple flags
            "Potassium {value} ** H mEq/L 3.5-5.0 CRITICAL",
            
            # Unusual formatting
            "{test_name}...{value}...{unit}...{range}",
            
            # Abbreviated units
            "WBC {value} K/uL 4.0-11.0",
            
            # No spaces around values
            "{test_name}{value}{unit} {range}"
        ]
        
        template = random.choice(edge_cases)
        
        # Fill in placeholders
        text = template.format(
            test_name=random.choice(self.test_names),
            value=random.choice(self.values),
            value1=random.choice(self.values[:10]),
            value2=random.choice(self.values[10:20]),
            unit=random.choice(self.units),
            range=random.choice(self.reference_ranges)
        )
        
        # Get rule-based labels
        labels = self.splitter.parse_to_bio_labels(text)
        
        return text, labels
    
    def generate_dataset(self, 
                        total_examples: int = 1000,
                        simple_ratio: float = 0.6,
                        complex_ratio: float = 0.3,
                        edge_ratio: float = 0.1) -> List[Tuple[str, List[str]]]:
        """Generate a complete dataset"""
        
        examples = []
        
        # Simple examples
        num_simple = int(total_examples * simple_ratio)
        for _ in range(num_simple):
            examples.append(self.generate_simple_test_row())
        
        # Complex examples  
        num_complex = int(total_examples * complex_ratio)
        for _ in range(num_complex):
            examples.append(self.generate_complex_test_row())
        
        # Edge cases
        num_edge = int(total_examples * edge_ratio)
        for _ in range(num_edge):
            examples.append(self.generate_edge_case())
        
        # Fill remaining with simple examples
        remaining = total_examples - len(examples)
        for _ in range(remaining):
            examples.append(self.generate_simple_test_row())
        
        # Shuffle dataset
        random.shuffle(examples)
        
        return examples
    
    def validate_examples(self, examples: List[Tuple[str, List[str]]]) -> Dict[str, int]:
        """Validate generated examples"""
        stats = {
            'total_examples': len(examples),
            'valid_examples': 0,
            'label_mismatches': 0,
            'empty_examples': 0,
            'label_distribution': {}
        }
        
        for text, labels in examples:
            words = text.split()
            
            if not text.strip():
                stats['empty_examples'] += 1
                continue
            
            if len(words) != len(labels):
                stats['label_mismatches'] += 1
                continue
            
            stats['valid_examples'] += 1
            
            # Count labels
            for label in labels:
                stats['label_distribution'][label] = stats['label_distribution'].get(label, 0) + 1
        
        return stats


def save_dataset(examples: List[Tuple[str, List[str]]], output_path: str):
    """Save dataset in training format"""
    data = []
    for text, labels in examples:
        data.append({
            'text': text,
            'labels': labels
        })
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Dataset saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate synthetic TEST_ROW training data')
    parser.add_argument('--output', '-o', default='/data/sample_testrow_data.json',
                       help='Output file path')
    parser.add_argument('--size', type=int, default=1000,
                       help='Number of examples to generate')
    parser.add_argument('--simple-ratio', type=float, default=0.6,
                       help='Ratio of simple examples')
    parser.add_argument('--complex-ratio', type=float, default=0.3,
                       help='Ratio of complex examples')
    parser.add_argument('--edge-ratio', type=float, default=0.1,
                       help='Ratio of edge cases')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed')
    
    args = parser.parse_args()
    
    # Validate ratios
    total_ratio = args.simple_ratio + args.complex_ratio + args.edge_ratio
    if abs(total_ratio - 1.0) > 0.01:
        print("Warning: Ratios don't sum to 1.0, normalizing...")
        args.simple_ratio /= total_ratio
        args.complex_ratio /= total_ratio
        args.edge_ratio /= total_ratio
    
    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating {args.size} synthetic TEST_ROW examples...")
    print(f"  Simple examples: {args.simple_ratio:.1%}")
    print(f"  Complex examples: {args.complex_ratio:.1%}")
    print(f"  Edge cases: {args.edge_ratio:.1%}")
    
    # Generate dataset
    generator = TestRowSampleGenerator(random_seed=args.seed)
    examples = generator.generate_dataset(
        total_examples=args.size,
        simple_ratio=args.simple_ratio,
        complex_ratio=args.complex_ratio,
        edge_ratio=args.edge_ratio
    )
    
    # Validate examples
    stats = generator.validate_examples(examples)
    
    print(f"\n=== Dataset Statistics ===")
    print(f"Total examples: {stats['total_examples']}")
    print(f"Valid examples: {stats['valid_examples']}")
    print(f"Label mismatches: {stats['label_mismatches']}")
    print(f"Empty examples: {stats['empty_examples']}")
    
    print(f"\nLabel distribution:")
    total_tokens = sum(stats['label_distribution'].values())
    for label in ['O'] + [l for l in stats['label_distribution'].keys() if l != 'O']:
        count = stats['label_distribution'].get(label, 0)
        percentage = (count / total_tokens) * 100 if total_tokens > 0 else 0
        print(f"  {label}: {count} ({percentage:.1f}%)")
    
    # Show sample examples
    print(f"\nSample examples:")
    for i, (text, labels) in enumerate(examples[:5]):
        print(f"\n  Example {i+1}:")
        print(f"    Text: {text}")
        words = text.split()
        labeled_words = [f"{word}:{label}" for word, label in zip(words, labels)]
        print(f"    Labels: {' '.join(labeled_words)}")
    
    # Save dataset
    save_dataset(examples, args.output)
    
    print(f"\n✅ Dataset generation complete!")
    print(f"Use for training: python train_testrow.py {args.output}")


if __name__ == '__main__':
    main()