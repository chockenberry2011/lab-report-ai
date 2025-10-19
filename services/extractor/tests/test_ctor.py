"""Test PDFExtractor constructor with various parameters"""

import pytest
from services.extractor.pdf_extractor import PDFExtractor


def test_pdf_extractor_constructor_defaults():
    """Test PDFExtractor constructor with default parameters"""
    extractor = PDFExtractor()
    
    assert extractor.dpi == 300
    assert extractor.ocr_dpi is None
    assert extractor.tesseract_lang == "eng"
    assert extractor.ocr_threshold == 25
    assert extractor.use_ocr_on_text_light_pages is False
    assert extractor.min_text_threshold == 25.0  # Legacy compatibility


def test_pdf_extractor_constructor_custom_params():
    """Test PDFExtractor constructor with custom parameters"""
    extractor = PDFExtractor(
        dpi=200,
        ocr_dpi=300,
        tesseract_lang="fra+eng",
        ocr_threshold=50,
        use_ocr_on_text_light_pages=True
    )
    
    assert extractor.dpi == 200
    assert extractor.ocr_dpi == 300
    assert extractor.tesseract_lang == "fra+eng"
    assert extractor.ocr_threshold == 50
    assert extractor.use_ocr_on_text_light_pages is True
    assert extractor.min_text_threshold == 50.0


def test_pdf_extractor_constructor_with_unknown_kwargs():
    """Test that PDFExtractor constructor ignores unknown kwargs"""
    # This should not crash even with unknown parameters
    extractor = PDFExtractor(
        dpi=200,
        ocr_dpi=300,
        foo="bar",
        some_unknown_param=123,
        another_param={"nested": "value"}
    )
    
    # Should still set the known parameters correctly
    assert extractor.dpi == 200
    assert extractor.ocr_dpi == 300
    assert extractor.tesseract_lang == "eng"  # Default
    
    # Unknown kwargs should be ignored (not stored)
    assert not hasattr(extractor, 'foo')
    assert not hasattr(extractor, 'some_unknown_param')
    assert not hasattr(extractor, 'another_param')


def test_pdf_extractor_legacy_compatibility():
    """Test that the old min_text_threshold parameter is still supported"""
    extractor = PDFExtractor(min_text_threshold=75.0)
    
    # Should prioritize min_text_threshold when provided
    assert extractor.ocr_threshold == 75  # Set from min_text_threshold
    assert extractor.min_text_threshold == 75.0  # Direct value
    
    # Test without min_text_threshold (uses ocr_threshold)
    extractor2 = PDFExtractor(ocr_threshold=50)
    assert extractor2.ocr_threshold == 50
    assert extractor2.min_text_threshold == 50.0
    
    
def test_pdf_extractor_type_hints():
    """Test that type hints work correctly"""
    # Test with int | None syntax for ocr_dpi
    extractor = PDFExtractor(ocr_dpi=None)
    assert extractor.ocr_dpi is None
    
    extractor2 = PDFExtractor(ocr_dpi=150)
    assert extractor2.ocr_dpi == 150