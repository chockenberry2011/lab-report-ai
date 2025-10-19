import os
import json
from pathlib import Path
from dataclasses import asdict

import redis
from celery import Celery

from .pdf_extractor import PDFExtractor
from .headers import HeaderFooterDetector

# Redis connection
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
app = Celery('extractor', broker=redis_url, backend=redis_url)

# Initialize extractors
pdf_extractor = PDFExtractor()
header_detector = HeaderFooterDetector()


@app.task
def extract_text(file_path):
    """Extract raw text from various file formats"""
    print(f"Extracting text from: {file_path}")
    
    try:
        if file_path.endswith('.pdf'):
            return extract_pdf_text(file_path)
        elif file_path.endswith('.docx'):
            return extract_docx_text(file_path)
        elif file_path.endswith(('.png', '.jpg', '.jpeg')):
            return extract_image_text(file_path)
        else:
            return {"error": "Unsupported file type"}
    except Exception as e:
        return {"error": f"Extraction failed: {str(e)}"}


@app.task
def extract_lines(file_path, output_dir="/data/outbox", mark_headers=True):
    """Extract structured lines from PDF and save to JSON"""
    print(f"Extracting lines from: {file_path}")
    
    try:
        if not file_path.endswith('.pdf'):
            return {"error": "Only PDF files supported for line extraction"}
        
        # Extract lines
        lines = pdf_extractor.extract_lines(file_path)
        
        if not lines:
            return {"error": "No lines extracted from PDF"}
        
        # Mark headers/footers if requested
        if mark_headers:
            lines = header_detector.mark_header_footer_lines(lines)
        
        # Prepare output
        pdf_name = Path(file_path).stem
        output_path = Path(output_dir) / f"{pdf_name}.lines.json"
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict format for JSON serialization
        lines_data = [asdict(line) for line in lines]
        
        # Add metadata
        output_data = {
            "source_file": file_path,
            "total_lines": len(lines_data),
            "pages": len(set(line["page"] for line in lines_data)),
            "has_header_footer_detection": mark_headers,
            "lines": lines_data
        }
        
        # Write JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        # Calculate statistics
        ocr_lines = sum(1 for line in lines_data if line.get("source") == "ocr")
        header_lines = sum(1 for line in lines_data if "PAGE_HEADER" in line.get("text", ""))
        footer_lines = sum(1 for line in lines_data if "PAGE_FOOTER" in line.get("text", ""))
        
        return {
            "success": True,
            "output_file": str(output_path),
            "total_lines": len(lines_data),
            "pages": len(set(line["page"] for line in lines_data)),
            "ocr_lines": ocr_lines,
            "header_lines": header_lines,
            "footer_lines": footer_lines
        }
        
    except Exception as e:
        return {"error": f"Line extraction failed: {str(e)}"}


def extract_pdf_text(file_path):
    """Extract raw text from PDF using advanced extractor"""
    try:
        text = pdf_extractor.extract_text(file_path)
        return {
            "text": text,
            "length": len(text),
            "source": "pdf_extractor"
        }
    except Exception as e:
        return {"error": f"PDF text extraction failed: {str(e)}"}


def extract_docx_text(file_path):
    """Extract text from DOCX files (placeholder implementation)"""
    # TODO: Implement DOCX extraction
    return {"text": "DOCX extraction not yet implemented"}


def extract_image_text(file_path):
    """Extract text from images using OCR (placeholder implementation)"""
    # TODO: Implement image OCR extraction
    return {"text": "Image OCR extraction not yet implemented"}


if __name__ == '__main__':
    # Also make CLI available when run directly
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'cli':
        from .cli import cli
        sys.argv = sys.argv[1:]  # Remove 'cli' from args
        cli()
    else:
        app.start()