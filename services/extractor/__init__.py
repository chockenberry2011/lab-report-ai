"""
PDF Extractor Service

Advanced PDF text extraction with OCR fallback and header/footer detection.
"""

try:
    from .pdf_extractor import PDFExtractor, LineData
    from .headers import HeaderFooterDetector, HeaderFooterResult
    __all__ = ["PDFExtractor", "LineData", "HeaderFooterDetector", "HeaderFooterResult"]
except ImportError:
    # Allow module loading even when dependencies aren't installed
    __all__ = []

__version__ = "1.0.0"