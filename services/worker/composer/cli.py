"""
CLI interface for the panel composer
"""

import json
import argparse
from pathlib import Path
from typing import Dict, Any

from .composer import PanelComposer
from .schemas import ComposerResult


def load_lines_data(input_file: str) -> list:
    """Load lines data from JSON file"""
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both extractor format and plain list format
    if isinstance(data, dict) and 'lines' in data:
        return data['lines']
    elif isinstance(data, list):
        return data
    else:
        raise ValueError("Invalid input format. Expected list or dict with 'lines' key.")


def save_result(result: ComposerResult, output_file: str, format_type: str = 'ehr'):
    """Save composer result to file"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if format_type == 'ehr':
        # Save as EHR-ready JSON
        content = result.to_ehr_json()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        # Save as raw result dict
        result_dict = {
            'panels': [panel.to_dict() for panel in result.panels],
            'processing_stats': {
                'total_lines_processed': result.total_lines_processed,
                'total_test_rows': result.total_test_rows,
                'page_breaks_handled': result.page_breaks_handled,
                'repairs_made': result.repairs_made,
                'processing_time': result.processing_time
            },
            'summary': result.get_summary()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description='Compose lab data into structured panels')
    
    parser.add_argument('input', help='Input JSON file with lines data')
    parser.add_argument('output', help='Output JSON file for composed panels')
    parser.add_argument('--format', choices=['ehr', 'raw'], default='ehr',
                       help='Output format (default: ehr)')
    parser.add_argument('--lookahead', type=int, default=8,
                       help='Page break lookahead lines (default: 8)')
    parser.add_argument('--min-continuity', type=float, default=0.3,
                       help='Minimum continuity score (default: 0.3)')
    parser.add_argument('--cost-switches', type=float, default=2.0,
                       help='Cost weight for panel switches (default: 2.0)')
    parser.add_argument('--cost-coherence', type=float, default=1.0,
                       help='Cost weight for coherence (default: 1.0)')
    parser.add_argument('--disable-scoring', action='store_true',
                       help='Disable confidence scoring')
    parser.add_argument('--value-threshold', type=float, default=0.7,
                       help='Value parse confidence threshold (default: 0.7)')
    parser.add_argument('--unit-threshold', type=float, default=0.8,
                       help='Unit validity confidence threshold (default: 0.8)')
    parser.add_argument('--range-threshold', type=float, default=0.6,
                       help='Reference range confidence threshold (default: 0.6)')
    parser.add_argument('--panel-threshold', type=float, default=0.7,
                       help='Panel confidence threshold (default: 0.7)')
    parser.add_argument('--document-threshold', type=float, default=0.75,
                       help='Document confidence threshold (default: 0.75)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    try:
        # Load input data
        if args.verbose:
            print(f"Loading lines data from {args.input}...")
        
        lines_data = load_lines_data(args.input)
        
        if args.verbose:
            print(f"Loaded {len(lines_data)} lines")
        
        # Initialize composer with scoring config
        scoring_config = {
            'value_parse_threshold': args.value_threshold,
            'unit_validity_threshold': args.unit_threshold,
            'ref_range_threshold': args.range_threshold,
            'panel_score_threshold': args.panel_threshold,
            'document_score_threshold': args.document_threshold
        }
        
        composer = PanelComposer(
            page_break_lookahead=args.lookahead,
            min_continuity_score=args.min_continuity,
            cost_weight_switches=args.cost_switches,
            cost_weight_coherence=args.cost_coherence,
            enable_scoring=not args.disable_scoring,
            scoring_config=scoring_config
        )
        
        # Compose panels
        if args.verbose:
            print("Composing panels...")
        
        result = composer.compose(lines_data)
        result.source_document = args.input
        
        # Save result
        if args.verbose:
            print(f"Saving result to {args.output}...")
        
        save_result(result, args.output, args.format)
        
        # Print summary
        summary = result.get_summary()
        print(f"\nComposition completed!")
        print(f"Total panels: {summary['total_panels']}")
        print(f"Total test rows: {summary['total_test_rows']}")
        print(f"Avg tests per panel: {summary['avg_tests_per_panel']:.1f}")
        print(f"Processing time: {summary['processing_time']:.2f}s")
        print(f"Page breaks handled: {result.page_breaks_handled}")
        print(f"Repairs made: {result.repairs_made}")
        
        # Print scoring information if enabled
        if not args.disable_scoring and result.document_score is not None:
            print(f"\nQuality Assessment:")
            print(f"Document score: {result.document_score:.3f}")
            print(f"Needs review: {'Yes' if result.needs_review else 'No'}")
            
            if result.review_reasons:
                print(f"Review reasons:")
                for reason in result.review_reasons:
                    print(f"  - {reason}")
            
            if result.confidence_distribution:
                dist = result.confidence_distribution
                print(f"Confidence distribution:")
                print(f"  Mean: {dist['mean']:.3f}")
                print(f"  Range: {dist['min']:.3f} - {dist['max']:.3f}")
            
            panels_needing_review = sum(1 for panel in result.panels if panel.needs_review)
            print(f"Panels needing review: {panels_needing_review}/{len(result.panels)}")
        
        if args.verbose:
            print(f"\nPanel details:")
            for i, panel in enumerate(result.panels, 1):
                review_status = " (REVIEW NEEDED)" if panel.needs_review else ""
                score_info = f" [Score: {panel.panel_score:.3f}]" if panel.panel_score is not None else ""
                print(f"  Panel {i}: {panel.name} ({len(panel.test_rows)} tests){score_info}{review_status}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
