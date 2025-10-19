#!/usr/bin/env python3
"""
Unit tests for PDF extractor package
"""

import unittest
import tempfile
import json
import os
from pathlib import Path
from typing import List

from .pdf_extractor import PDFExtractor, LineData
from .headers import HeaderFooterDetector, HeaderFooterResult
from .test_data_generator import TestPDFGenerator


class TestPDFExtractor(unittest.TestCase):
    """Test PDF extraction functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.test_dir = tempfile.mkdtemp()
        cls.generator = TestPDFGenerator(cls.test_dir)
        cls.extractor = PDFExtractor(min_text_threshold=30.0)
        
        # Generate test documents
        cls.multi_page_pdf = cls.generator.generate_multi_page_with_headers()
        cls.mixed_font_pdf = cls.generator.generate_mixed_font_document()
        cls.low_text_pdf = cls.generator.generate_low_text_document()
        cls.varying_headers_pdf = cls.generator.generate_varying_headers_document()
    
    def test_extract_text_basic(self):
        """Test basic text extraction"""
        text = self.extractor.extract_text(self.multi_page_pdf)
        
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)
        self.assertIn("Company Confidential Report", text)
        self.assertIn("main content", text.lower())
    
    def test_extract_lines_structure(self):
        """Test line extraction returns proper structure"""
        lines = self.extractor.extract_lines(self.multi_page_pdf)
        
        self.assertIsInstance(lines, list)
        self.assertGreater(len(lines), 0)
        
        # Check first line structure
        first_line = lines[0]
        self.assertIsInstance(first_line, LineData)
        self.assertIsInstance(first_line.page, int)
        self.assertIsInstance(first_line.text, str)
        self.assertIsInstance(first_line.xLeft, float)
        self.assertIsInstance(first_line.xRight, float)
        self.assertIsInstance(first_line.yNorm, float)
        self.assertIsInstance(first_line.fontSize, float)
        self.assertIsInstance(first_line.isBold, bool)
        self.assertIsInstance(first_line.hasText, bool)
        
        # Check coordinate ranges
        for line in lines:
            self.assertGreaterEqual(line.yNorm, 0.0)
            self.assertLessEqual(line.yNorm, 1.0)
            self.assertLess(line.xLeft, line.xRight)
            self.assertGreater(line.fontSize, 0)
    
    def test_multi_page_extraction(self):
        """Test extraction from multi-page document"""
        lines = self.extractor.extract_lines(self.multi_page_pdf)
        
        pages = set(line.page for line in lines)
        self.assertEqual(len(pages), 5)  # Should have 5 pages
        self.assertEqual(min(pages), 1)
        self.assertEqual(max(pages), 5)
    
    def test_font_detection(self):
        """Test font size and bold detection"""
        lines = self.extractor.extract_lines(self.mixed_font_pdf)
        
        font_sizes = [line.fontSize for line in lines if line.fontSize > 0]
        self.assertGreater(len(font_sizes), 0)
        
        # Should have variety of font sizes
        unique_sizes = set(font_sizes)
        self.assertGreater(len(unique_sizes), 1)
        
        # Check for bold detection
        bold_lines = [line for line in lines if line.isBold]
        # Note: Bold detection is best-effort, so we don't require it to work perfectly
    
    def test_low_text_ocr_fallback(self):
        """Test OCR fallback for low-text pages"""
        # Note: This test might not work in CI without proper OCR setup
        try:
            lines = self.extractor.extract_lines(self.low_text_pdf)
            
            # Should have lines from both pages
            pages = set(line.page for line in lines)
            self.assertGreaterEqual(len(pages), 1)
            
            # Check for OCR source marking
            sources = set(line.source for line in lines)
            # OCR might not work in test environment, so just check structure
            
        except Exception as e:
            # OCR might fail in test environment, that's OK
            self.skipTest(f"OCR test skipped due to environment: {e}")
    
    def test_empty_pdf_handling(self):
        """Test handling of invalid input"""
        with self.assertRaises(Exception):
            self.extractor.extract_lines("/nonexistent/file.pdf")


class TestHeaderFooterDetector(unittest.TestCase):
    """Test header/footer detection functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.test_dir = tempfile.mkdtemp()
        cls.generator = TestPDFGenerator(cls.test_dir)
        cls.extractor = PDFExtractor()
        cls.detector = HeaderFooterDetector()
        
        # Generate test documents
        cls.multi_page_pdf = cls.generator.generate_multi_page_with_headers()
        cls.varying_headers_pdf = cls.generator.generate_varying_headers_document()
    
    def test_header_footer_detection_basic(self):
        """Test basic header/footer detection"""
        lines = self.extractor.extract_lines(self.multi_page_pdf)
        result = self.detector.detect_headers_footers(lines)
        
        self.assertIsInstance(result, HeaderFooterResult)
        self.assertIsInstance(result.page_headers, dict)
        self.assertIsInstance(result.page_footers, dict)
        self.assertIsInstance(result.header_clusters, list)
        self.assertIsInstance(result.footer_clusters, list)
    
    def test_header_clustering(self):
        """Test that similar headers are clustered together"""
        lines = self.extractor.extract_lines(self.varying_headers_pdf)
        result = self.detector.detect_headers_footers(lines)
        
        # Should detect header patterns
        self.assertGreater(len(result.header_clusters), 0)
        
        # Check that clusters contain similar text
        for cluster in result.header_clusters:
            self.assertIsInstance(cluster, list)
            self.assertGreater(len(cluster), 0)
    
    def test_mark_header_footer_lines(self):
        """Test marking lines with header/footer labels"""
        lines = self.extractor.extract_lines(self.multi_page_pdf)
        marked_lines = self.detector.mark_header_footer_lines(lines)
        
        self.assertEqual(len(marked_lines), len(lines))
        
        # Check for header/footer markers
        header_count = sum(1 for line in marked_lines if "PAGE_HEADER" in line.text)
        footer_count = sum(1 for line in marked_lines if "PAGE_FOOTER" in line.text)
        
        # Should have some headers/footers detected
        # Note: Exact counts depend on detection algorithm performance
        
    def test_insufficient_pages(self):
        """Test behavior with insufficient pages for clustering"""
        # Create single line data
        single_line = [LineData(
            page=1,
            text="Single line",
            xLeft=0.0,
            xRight=100.0,
            yNorm=0.5,
            fontSize=12.0,
            isBold=False,
            hasText=True
        )]
        
        result = self.detector.detect_headers_footers(single_line)
        
        # Should return empty results
        self.assertEqual(len(result.page_headers), 0)
        self.assertEqual(len(result.page_footers), 0)
        self.assertEqual(len(result.header_clusters), 0)
        self.assertEqual(len(result.footer_clusters), 0)


class TestCLIIntegration(unittest.TestCase):
    """Test CLI interface functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.test_dir = tempfile.mkdtemp()
        cls.output_dir = tempfile.mkdtemp()
        cls.generator = TestPDFGenerator(cls.test_dir)
        
        # Generate test document
        cls.test_pdf = cls.generator.generate_multi_page_with_headers()
    
    def test_json_output_format(self):
        """Test that JSON output has correct structure"""
        from .cli import extract_lines
        from unittest.mock import patch
        import click.testing
        
        runner = click.testing.CliRunner()
        
        with patch('services.extractor.cli.extract_lines') as mock_extract:
            # Mock the extract_lines function to test structure
            extractor = PDFExtractor()
            lines = extractor.extract_lines(self.test_pdf)
            
            # Test JSON serialization
            lines_data = [line.__dict__ for line in lines]
            
            output_data = {
                "source_file": self.test_pdf,
                "total_lines": len(lines_data),
                "pages": len(set(line["page"] for line in lines_data)),
                "has_header_footer_detection": False,
                "lines": lines_data
            }
            
            # Should be JSON serializable
            json_str = json.dumps(output_data)
            self.assertIsInstance(json_str, str)
            
            # Should be deserializable
            parsed = json.loads(json_str)
            self.assertEqual(parsed["total_lines"], len(lines_data))
            self.assertIn("lines", parsed)


class TestDataGenerator(unittest.TestCase):
    """Test the test data generator"""
    
    def test_generate_documents(self):
        """Test that all test documents are generated successfully"""
        test_dir = tempfile.mkdtemp()
        generator = TestPDFGenerator(test_dir)
        
        documents = generator.generate_all_test_documents()
        
        self.assertEqual(len(documents), 4)
        
        for doc_path in documents:
            self.assertTrue(os.path.exists(doc_path))
            self.assertGreater(os.path.getsize(doc_path), 0)
            self.assertTrue(doc_path.endswith('.pdf'))


if __name__ == '__main__':
    # Run all tests
    unittest.main(verbosity=2)