#!/usr/bin/env python3
"""
Generate sample training data for line role classifier

Creates synthetic medical document lines for testing and development.
"""

import json
import random
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import asdict

try:
    from .line_classifier import LineData, ROLE_LABELS, calculate_y_tertile, detect_header_hints
except ImportError:  # fallback when run as a plain script
    from line_classifier import LineData, ROLE_LABELS, calculate_y_tertile, detect_header_hints


class SampleDataGenerator:
    """Generate synthetic training data for medical documents"""
    
    def __init__(self, random_seed: int = 42):
        random.seed(random_seed)
        self.templates = self._create_templates()
    
    def _create_templates(self) -> Dict[str, List[Dict[str, Any]]]:
        """Create templates for each role type"""
        return {
            'PAGE_HEADER': [
                {'text': 'LABORATORY REPORT', 'y_norm': 0.95, 'is_bold': True, 'font_size': 14},
                {'text': 'Medical Center Lab Results', 'y_norm': 0.92, 'is_bold': True, 'font_size': 12},
                {'text': 'LAB RESULTS - CONFIDENTIAL', 'y_norm': 0.94, 'is_bold': True, 'font_size': 13},
                {'text': 'Clinical Laboratory Report', 'y_norm': 0.93, 'is_bold': False, 'font_size': 12},
            ],
            
            'PAGE_FOOTER': [
                {'text': 'Page 1 of 2', 'y_norm': 0.05, 'is_bold': False, 'font_size': 10},
                {'text': '© 2024 Medical Center', 'y_norm': 0.03, 'is_bold': False, 'font_size': 9},
                {'text': 'Confidential Patient Information', 'y_norm': 0.04, 'is_bold': False, 'font_size': 9},
                {'text': 'Report Generated: 03/15/2024', 'y_norm': 0.06, 'is_bold': False, 'font_size': 10},
            ],
            
            'HEADER_PATIENT': [
                {'text': 'Patient: Smith, John', 'y_norm': 0.85, 'is_bold': True, 'font_size': 12},
                {'text': 'Name: Doe, Jane', 'y_norm': 0.87, 'is_bold': False, 'font_size': 11},
                {'text': 'DOB: 01/15/1985', 'y_norm': 0.84, 'is_bold': False, 'font_size': 11},
                {'text': 'MRN: 12345678', 'y_norm': 0.82, 'is_bold': False, 'font_size': 11},
                {'text': 'Patient ID: ABC123456', 'y_norm': 0.83, 'is_bold': False, 'font_size': 11},
            ],
            
            'HEADER_SPECIMEN': [
                {'text': 'Specimen: Blood', 'y_norm': 0.78, 'is_bold': True, 'font_size': 12},
                {'text': 'Collection Date: 03/14/2024', 'y_norm': 0.76, 'is_bold': False, 'font_size': 11},
                {'text': 'Received: 03/14/2024 2:30 PM', 'y_norm': 0.75, 'is_bold': False, 'font_size': 11},
                {'text': 'Accession #: LAB2024001234', 'y_norm': 0.77, 'is_bold': False, 'font_size': 11},
                {'text': 'Specimen Type: Serum', 'y_norm': 0.74, 'is_bold': False, 'font_size': 11},
            ],
            
            'SECTION_PANEL': [
                {'text': 'COMPREHENSIVE METABOLIC PANEL', 'y_norm': 0.65, 'is_bold': True, 'font_size': 12},
                {'text': 'LIPID PANEL', 'y_norm': 0.55, 'is_bold': True, 'font_size': 12},
                {'text': 'COMPLETE BLOOD COUNT', 'y_norm': 0.45, 'is_bold': True, 'font_size': 12},
                {'text': 'THYROID FUNCTION TESTS', 'y_norm': 0.35, 'is_bold': True, 'font_size': 12},
                {'text': 'LIVER FUNCTION PANEL', 'y_norm': 0.25, 'is_bold': True, 'font_size': 12},
            ],
            
            'TEST_ROW': [
                {'text': 'Glucose                    95        mg/dL       70-100', 'y_norm': 0.62, 'is_bold': False, 'font_size': 10},
                {'text': 'Cholesterol, Total         180       mg/dL       <200', 'y_norm': 0.60, 'is_bold': False, 'font_size': 10},
                {'text': 'Hemoglobin                 14.2      g/dL        12.0-16.0', 'y_norm': 0.58, 'is_bold': False, 'font_size': 10},
                {'text': 'White Blood Cell Count     6.8       K/uL        4.0-11.0', 'y_norm': 0.56, 'is_bold': False, 'font_size': 10},
                {'text': 'Creatinine                 1.0       mg/dL       0.7-1.3', 'y_norm': 0.54, 'is_bold': False, 'font_size': 10},
                {'text': 'ALT (SGPT)                 25        U/L         7-56', 'y_norm': 0.52, 'is_bold': False, 'font_size': 10},
            ],
            
            'COMMENT': [
                {'text': '* Reference ranges are for adults.', 'y_norm': 0.48, 'is_bold': False, 'font_size': 9},
                {'text': 'Note: Patient was fasting for 12 hours.', 'y_norm': 0.46, 'is_bold': False, 'font_size': 9},
                {'text': 'Critical value called to Dr. Johnson at 3:45 PM', 'y_norm': 0.44, 'is_bold': False, 'font_size': 9},
                {'text': '** Abnormal result - recommend follow-up', 'y_norm': 0.42, 'is_bold': True, 'font_size': 9},
                {'text': 'Results reviewed and verified by Lab Director', 'y_norm': 0.40, 'is_bold': False, 'font_size': 9},
            ],
            
            'SECTION_MISC': [
                {'text': 'Ordering Provider: Dr. Sarah Johnson', 'y_norm': 0.70, 'is_bold': False, 'font_size': 11},
                {'text': 'Department: Internal Medicine', 'y_norm': 0.68, 'is_bold': False, 'font_size': 11},
                {'text': 'Report Status: Final', 'y_norm': 0.20, 'is_bold': False, 'font_size': 11},
                {'text': 'Lab Director: Dr. Michael Chen, MD', 'y_norm': 0.18, 'is_bold': False, 'font_size': 11},
                {'text': 'Electronically signed on 03/15/2024', 'y_norm': 0.15, 'is_bold': False, 'font_size': 10},
            ],
            
            'JUNK': [
                {'text': '                    ', 'y_norm': 0.30, 'is_bold': False, 'font_size': 10},
                {'text': '___________________', 'y_norm': 0.28, 'is_bold': False, 'font_size': 10},
                {'text': '...', 'y_norm': 0.26, 'is_bold': False, 'font_size': 10},
                {'text': 'Page Break', 'y_norm': 0.50, 'is_bold': False, 'font_size': 8},
                {'text': '||||||||||||||||', 'y_norm': 0.24, 'is_bold': False, 'font_size': 10},
            ]
        }
    
    def generate_line(self, role: str, page: int = 1) -> LineData:
        """Generate a single line for the specified role"""
        if role not in self.templates:
            raise ValueError(f"Unknown role: {role}")
        
        # Select random template
        template = random.choice(self.templates[role])
        
        # Add some variation
        text = template['text']
        y_norm = template['y_norm'] + random.uniform(-0.05, 0.05)  # Small variation
        y_norm = max(0.0, min(1.0, y_norm))  # Clamp to valid range
        
        is_bold = template['is_bold']
        font_size = template['font_size'] + random.uniform(-1, 1)
        
        # Generate x coordinates
        x_left = random.uniform(50, 100)
        x_right = x_left + len(text) * 5 + random.uniform(0, 50)
        
        # Auto-detect header hints
        is_header_hint = detect_header_hints(text)
        
        return LineData(
            text=text,
            y_tertile=calculate_y_tertile(y_norm),
            is_bold=is_bold,
            is_header_hint=is_header_hint,
            role=role,
            page=page,
            x_left=x_left,
            x_right=x_right,
            y_norm=y_norm,
            font_size=font_size
        )
    
    def generate_document(self, num_pages: int = 2) -> List[LineData]:
        """Generate a complete document with multiple pages"""
        lines = []
        
        for page in range(1, num_pages + 1):
            # Add page header
            lines.append(self.generate_line('PAGE_HEADER', page))
            
            # Add patient info (only on first page)
            if page == 1:
                lines.extend([
                    self.generate_line('HEADER_PATIENT', page),
                    self.generate_line('HEADER_PATIENT', page),  # DOB, MRN, etc.
                    self.generate_line('HEADER_SPECIMEN', page),
                    self.generate_line('HEADER_SPECIMEN', page),
                ])
            
            # Add test panels and results
            num_panels = random.randint(2, 4)
            for _ in range(num_panels):
                # Panel header
                lines.append(self.generate_line('SECTION_PANEL', page))
                
                # Test results
                num_tests = random.randint(3, 8)
                for _ in range(num_tests):
                    lines.append(self.generate_line('TEST_ROW', page))
                
                # Occasional comments
                if random.random() < 0.3:
                    lines.append(self.generate_line('COMMENT', page))
            
            # Add some misc sections
            if random.random() < 0.5:
                lines.append(self.generate_line('SECTION_MISC', page))
            
            # Add occasional junk
            if random.random() < 0.2:
                lines.append(self.generate_line('JUNK', page))
            
            # Add page footer
            lines.append(self.generate_line('PAGE_FOOTER', page))
        
        return lines
    
    def generate_balanced_dataset(self, total_samples: int = 1000) -> List[LineData]:
        """Generate a balanced dataset with roughly equal representation"""
        lines = []
        samples_per_role = total_samples // len(ROLE_LABELS)
        
        for role in ROLE_LABELS:
            for _ in range(samples_per_role):
                page = random.randint(1, 3)
                line = self.generate_line(role, page)
                lines.append(line)
        
        # Add some extra samples to reach target
        remaining = total_samples - len(lines)
        for _ in range(remaining):
            role = random.choice(ROLE_LABELS)
            page = random.randint(1, 3)
            line = self.generate_line(role, page)
            lines.append(line)
        
        # Shuffle the dataset
        random.shuffle(lines)
        return lines
    
    def generate_realistic_dataset(self, num_documents: int = 50) -> List[LineData]:
        """Generate realistic dataset with natural role distributions"""
        all_lines = []
        
        for _ in range(num_documents):
            doc_lines = self.generate_document(num_pages=random.randint(1, 3))
            all_lines.extend(doc_lines)
        
        random.shuffle(all_lines)
        return all_lines


def save_sample_data(lines: List[LineData], output_path: str):
    """Save sample data in the format expected by the training scripts"""
    data = []
    for line in lines:
        line_dict = asdict(line)
        data.append(line_dict)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Sample data saved to {output_path}")
    
    # Print statistics
    role_counts = {}
    for line in lines:
        role_counts[line.role] = role_counts.get(line.role, 0) + 1
    
    print(f"\nGenerated {len(lines)} samples:")
    for role, count in sorted(role_counts.items()):
        percentage = (count / len(lines)) * 100
        print(f"  {role}: {count} ({percentage:.1f}%)")


def main():
    """Generate sample data for development and testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate sample training data')
    parser.add_argument('--output', '-o', default='/data/sample_roles_data.json',
                       help='Output file path')
    parser.add_argument('--type', choices=['balanced', 'realistic'], default='realistic',
                       help='Type of dataset to generate')
    parser.add_argument('--size', type=int, default=1000,
                       help='Number of samples (for balanced) or documents (for realistic)')
    parser.add_argument('--seed', type=int, default=42,
                       help='Random seed for reproducibility')
    
    args = parser.parse_args()
    
    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating {args.type} dataset with size {args.size}")
    
    # Generate data
    generator = SampleDataGenerator(random_seed=args.seed)
    
    if args.type == 'balanced':
        lines = generator.generate_balanced_dataset(args.size)
    else:  # realistic
        lines = generator.generate_realistic_dataset(args.size)
    
    # Save data
    save_sample_data(lines, args.output)
    
    print(f"\n✅ Sample data generation complete!")
    print(f"Use this data for training: python train_roles.py {args.output}")


if __name__ == '__main__':
    main()