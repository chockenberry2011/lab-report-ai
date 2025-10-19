#!/usr/bin/env python3
"""
CLI interface for PDF text extraction
"""

import os
import json
import sys
import argparse
from pathlib import Path
from typing import List
from dataclasses import asdict

try:
    from .headers import HeaderFooterDetector
    def detect_headers(lines): 
        detector = HeaderFooterDetector()
        return detector.mark_header_footer_lines(lines)
except Exception:
    def detect_headers(lines): 
        return lines


def extract_text_command(args):
    """Extract raw text from PDF and print to stdout"""
    try:
        from .pdf_extractor import PDFExtractor
        
        # Create extractor with force_ocr flag if specified
        force_ocr = getattr(args, 'force_ocr', False)
        extractor = PDFExtractor(force_ocr=force_ocr)
        text = extractor.extract_text(args.pdf)
        # Join line texts as requested
        if hasattr(extractor, 'extract_lines'):
            lines = extractor.extract_lines(args.pdf)
            text = '\n'.join(line.text for line in lines if line.text.strip())
        print(text)
    except Exception as e:
        print(f"Error extracting text: {e}", file=sys.stderr)
        sys.exit(1)


def extract_lines_command(args):
    """Extract lines from PDF and save to JSON in output directory"""
    try:
        # Extract lines
        from .pdf_extractor import PDFExtractor
        from dataclasses import asdict
        
        # Create extractor with force_ocr flag if specified
        force_ocr = getattr(args, 'force_ocr', False)
        extractor = PDFExtractor(force_ocr=force_ocr)
        lines = extractor.extract_lines(args.pdf)
        
        if not lines:
            print("No lines extracted from PDF", file=sys.stderr)
            sys.exit(1)
        
        # Mark headers/footers if available
        try:
            lines = detect_headers(lines)
        except Exception:
            pass  # Continue without header detection
        
        # Prepare output
        pdf_name = Path(args.pdf).stem
        output_dir = getattr(args, 'output_dir', '/data/outbox')
        output_path = Path(output_dir) / f"{pdf_name}.lines.json"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict format for JSON serialization
        lines_data = [asdict(line) for line in lines]
        
        # Add metadata
        output_data = {
            "source_file": args.pdf,
            "total_lines": len(lines_data),
            "pages": len(set(line["page"] for line in lines_data)),
            "has_header_footer_detection": True,
            "lines": lines_data
        }
        
        # Write JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"Extracted {len(lines_data)} lines to {output_path}")
        
        # Print summary statistics
        ocr_lines = sum(1 for line in lines_data if line.get("source") == "ocr")
        if ocr_lines > 0:
            print(f"  {ocr_lines} lines extracted via OCR")
        
        header_lines = sum(1 for line in lines_data if "PAGE_HEADER" in line.get("text", ""))
        footer_lines = sum(1 for line in lines_data if "PAGE_FOOTER" in line.get("text", ""))
        if header_lines > 0 or footer_lines > 0:
            print(f"  {header_lines} header lines, {footer_lines} footer lines detected")
        
    except Exception as e:
        print(f"Error extracting lines: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description='PDF Text Extraction CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # extract_text subcommand
    text_parser = subparsers.add_parser('extract_text', help='Extract plain text from PDF')
    text_parser.add_argument('pdf', help='Path to PDF file')
    text_parser.add_argument('--force-ocr', action='store_true', help='Force OCR processing even for text-rich pages')
    text_parser.set_defaults(func=extract_text_command)
    
    # extract_lines subcommand  
    lines_parser = subparsers.add_parser('extract_lines', help='Extract structured lines from PDF')
    lines_parser.add_argument('pdf', help='Path to PDF file')
    lines_parser.add_argument('--output-dir', default='/data/outbox', help='Output directory for JSON files')
    lines_parser.add_argument('--force-ocr', action='store_true', help='Force OCR processing even for text-rich pages')
    lines_parser.set_defaults(func=extract_lines_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == '__main__':
    main()