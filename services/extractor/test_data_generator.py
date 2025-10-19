"""
Generate synthetic multi-page PDF documents for testing
"""

import os
from pathlib import Path
from fpdf import FPDF
from typing import List, Tuple


class TestPDFGenerator:
    """Generate test PDF documents with known structure"""
    
    def __init__(self, output_dir: str = "/tmp/test_pdfs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_multi_page_with_headers(self, filename: str = "test_headers.pdf", pages: int = 5) -> str:
        """Generate a multi-page PDF with consistent headers and footers"""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        
        header_text = "Company Confidential Report"
        footer_text = "© 2024 Test Company"
        
        for page_num in range(1, pages + 1):
            pdf.add_page()
            
            # Header
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, header_text, ln=True, align='C')
            pdf.ln(5)
            
            # Body content
            pdf.set_font('Arial', '', 11)
            pdf.cell(0, 10, f"Page {page_num} Content", ln=True)
            pdf.ln(5)
            
            # Add some sample content
            content_lines = [
                "This is the main content of the document.",
                "It contains multiple paragraphs with varying text.",
                "Some lines might be longer than others to test text extraction.",
                "The extraction system should handle different font sizes.",
                "",
                "Here's a second paragraph with more content.",
                "Testing line detection and coordinate extraction.",
            ]
            
            for line in content_lines:
                if line:
                    pdf.cell(0, 6, line, ln=True)
                else:
                    pdf.ln(3)
            
            # Footer (positioned at bottom)
            pdf.ln(10)
            pdf.set_font('Arial', 'I', 9)
            pdf.cell(0, 10, f"{footer_text} - Page {page_num}", ln=True, align='C')
        
        output_path = self.output_dir / filename
        pdf.output(str(output_path))
        return str(output_path)
    
    def generate_mixed_font_document(self, filename: str = "test_fonts.pdf") -> str:
        """Generate PDF with different font sizes and bold text"""
        pdf = FPDF()
        pdf.add_page()
        
        # Title
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 15, "Document with Mixed Fonts", ln=True, align='C')
        pdf.ln(10)
        
        # Various font sizes and styles
        fonts_and_text = [
            ('Arial', 'B', 14, "Bold Heading Text"),
            ('Arial', '', 12, "Regular paragraph text here"),
            ('Arial', 'I', 11, "Italic text for emphasis"),
            ('Arial', '', 10, "Smaller text at 10pt"),
            ('Arial', 'B', 8, "Small bold text"),
        ]
        
        for font_family, style, size, text in fonts_and_text:
            pdf.set_font(font_family, style, size)
            pdf.cell(0, size + 2, text, ln=True)
            pdf.ln(2)
        
        output_path = self.output_dir / filename
        pdf.output(str(output_path))
        return str(output_path)
    
    def generate_low_text_document(self, filename: str = "test_low_text.pdf") -> str:
        """Generate PDF with very minimal text (to trigger OCR)"""
        pdf = FPDF()
        pdf.add_page()
        
        # Very minimal text
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 10, "Hi", ln=True)
        
        # Add a second page with more content
        pdf.add_page()
        pdf.cell(0, 10, "Page 2 with more substantial content", ln=True)
        pdf.cell(0, 10, "This page should have enough text to avoid OCR", ln=True)
        pdf.cell(0, 10, "Multiple lines of content here to reach threshold", ln=True)
        
        output_path = self.output_dir / filename
        pdf.output(str(output_path))
        return str(output_path)
    
    def generate_varying_headers_document(self, filename: str = "test_varying_headers.pdf") -> str:
        """Generate PDF with similar but slightly different headers"""
        pdf = FPDF()
        
        headers = [
            "Quarterly Report - Q1 2024",
            "Quarterly Report - Q2 2024", 
            "Quarterly Report - Q3 2024",
        ]
        
        for i, header in enumerate(headers, 1):
            pdf.add_page()
            
            # Header
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, header, ln=True, align='C')
            pdf.ln(5)
            
            # Content
            pdf.set_font('Arial', '', 11)
            pdf.cell(0, 10, f"Content for quarter {i}", ln=True)
            pdf.cell(0, 10, "Sales figures and performance metrics", ln=True)
            pdf.cell(0, 10, "Revenue increased compared to previous quarter", ln=True)
            
            # Footer
            pdf.ln(20)
            pdf.set_font('Arial', 'I', 9)
            pdf.cell(0, 10, f"Page {i} of 3", ln=True, align='C')
        
        output_path = self.output_dir / filename
        pdf.output(str(output_path))
        return str(output_path)
    
    def generate_all_test_documents(self) -> List[str]:
        """Generate all test documents and return their paths"""
        documents = [
            self.generate_multi_page_with_headers(),
            self.generate_mixed_font_document(),
            self.generate_low_text_document(),
            self.generate_varying_headers_document(),
        ]
        
        print(f"Generated {len(documents)} test PDFs in {self.output_dir}")
        for doc in documents:
            print(f"  {Path(doc).name}")
        
        return documents


if __name__ == "__main__":
    generator = TestPDFGenerator()
    generator.generate_all_test_documents()