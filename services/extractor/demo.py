#!/usr/bin/env python3
"""
Demo script to test PDF extractor functionality
"""

import os
import sys
import tempfile
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .test_data_generator import TestPDFGenerator
from .pdf_extractor import PDFExtractor
from .headers import HeaderFooterDetector


def main():
    print("🔧 PDF Extractor Demo")
    print("=" * 50)
    
    # Create test directory
    test_dir = tempfile.mkdtemp()
    print(f"Using test directory: {test_dir}")
    
    # Generate test documents
    print("\n📝 Generating test documents...")
    generator = TestPDFGenerator(test_dir)
    
    test_pdfs = [
        generator.generate_multi_page_with_headers("demo_headers.pdf", pages=3),
        generator.generate_mixed_font_document("demo_fonts.pdf"),
        generator.generate_low_text_document("demo_ocr.pdf"),
    ]
    
    print(f"Generated {len(test_pdfs)} test PDFs")
    
    # Initialize extractor and detector
    extractor = PDFExtractor(min_text_threshold=30.0)
    detector = HeaderFooterDetector()
    
    # Test each document
    for pdf_path in test_pdfs:
        pdf_name = Path(pdf_path).name
        print(f"\n📖 Processing {pdf_name}...")
        
        try:
            # Extract text
            text = extractor.extract_text(pdf_path)
            print(f"  Raw text: {len(text)} characters")
            
            # Extract lines
            lines = extractor.extract_lines(pdf_path)
            print(f"  Structured lines: {len(lines)}")
            
            # Analyze pages
            pages = set(line.page for line in lines)
            print(f"  Pages: {sorted(pages)}")
            
            # Check for OCR usage
            ocr_lines = [line for line in lines if line.source == "ocr"]
            if ocr_lines:
                print(f"  OCR lines: {len(ocr_lines)}")
            
            # Font analysis
            font_sizes = [line.fontSize for line in lines if line.fontSize > 0]
            if font_sizes:
                print(f"  Font sizes: {min(font_sizes):.1f} - {max(font_sizes):.1f} pt")
            
            bold_lines = [line for line in lines if line.isBold]
            if bold_lines:
                print(f"  Bold lines: {len(bold_lines)}")
            
            # Header/footer detection
            if len(pages) > 1:  # Only for multi-page documents
                result = detector.detect_headers_footers(lines)
                if result.header_clusters or result.footer_clusters:
                    print(f"  Header clusters: {len(result.header_clusters)}")
                    print(f"  Footer clusters: {len(result.footer_clusters)}")
                    
                    # Show first header cluster
                    if result.header_clusters:
                        first_cluster = result.header_clusters[0]
                        print(f"  Sample header: {first_cluster[0][:50]}...")
        
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    print(f"\n✅ Demo completed. Test files in: {test_dir}")
    print("\nTo test CLI commands:")
    print(f"  python -m services.extractor extract_text {test_pdfs[0]}")
    print(f"  python -m services.extractor extract_lines {test_pdfs[0]}")
    print(f"  # analyze-headers command available via legacy CLI")


if __name__ == "__main__":
    main()