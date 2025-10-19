from __future__ import annotations

import os
import json
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict
import io
from pathlib import Path

# Lazy PDF imports - only imported when needed
_pdf_imports_attempted = False
_pdf_available = False
_pdf_error_msg = None

def _ensure_pdf_imports():
    """Lazily import PDF dependencies and check if they're available"""
    global _pdf_imports_attempted, _pdf_available, _pdf_error_msg
    
    if _pdf_imports_attempted:
        return _pdf_available
    
    _pdf_imports_attempted = True
    
    try:
        global extract_pages, LTTextContainer, LTTextBox, LTTextLine, LTTextLineHorizontal, LTChar, LTPage, LTFigure, LAParams, open_filename
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer, LTTextBox, LTTextLine, LTTextLineHorizontal, LTChar, LTPage, LTFigure, LAParams
        from pdfminer.utils import open_filename
        
        _pdf_available = True
        return True
        
    except ImportError as e:
        _pdf_error_msg = f"PDF dependencies not installed: {e}"
        return False
    except Exception as e:
        _pdf_error_msg = f"PDF initialization failed: {e}"
        return False

# Lazy OCR imports - only imported when needed
_ocr_imports_attempted = False
_ocr_available = False
_ocr_error_msg = None

def _ensure_ocr_imports():
    """Lazily import OCR dependencies and check if they're available"""
    global _ocr_imports_attempted, _ocr_available, _ocr_error_msg
    
    if _ocr_imports_attempted:
        return _ocr_available
    
    _ocr_imports_attempted = True
    
    try:
        global pdf2image, pytesseract, Image, np
        from pdf2image import convert_from_path as pdf2image
        import pytesseract
        from PIL import Image
        import numpy as np
        
        # Test if tesseract binary is available
        pytesseract.get_tesseract_version()
        _ocr_available = True
        return True
        
    except ImportError as e:
        _ocr_error_msg = f"OCR dependencies not installed: {e}"
        return False
    except pytesseract.TesseractNotFoundError as e:
        _ocr_error_msg = f"Tesseract binary not found: {e}"
        return False
    except Exception as e:
        _ocr_error_msg = f"OCR initialization failed: {e}"
        return False


@dataclass
class LineData:
    """Structure for extracted line data"""
    page: int
    text: str
    xLeft: float
    xRight: float
    yNorm: float  # 0..1 normalized from bottom
    fontSize: float
    isBold: bool
    hasText: bool
    source: str = "pdf"  # "pdf" or "ocr"


def _apply_header_quarantine_safely(lines):
    """Wrap header/footer quarantine so it can't empty results"""
    try:
        body, hdr = _quarantine_headers_footers(lines)  # your existing function
        # safety: never let quarantine return empty if we had content
        return (body or lines), (hdr or [])
    except Exception:
        # safety: if heuristic explodes, keep original lines
        return lines, []


def _quarantine_headers_footers(lines: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Basic header/footer quarantine implementation"""
    if len(lines) < 10:
        return lines, []
    
    body = []
    quarantined = []
    
    for line in lines:
        # Basic heuristics for header/footer detection
        text = line.get('text', '').strip().lower()
        y_norm = line.get('yNorm', 0.5)
        
        # Quarantine if very top or bottom of page, or contains header/footer patterns
        is_header_footer = (
            y_norm > 0.95 or y_norm < 0.05 or  # Very top/bottom
            any(pattern in text for pattern in ['page', 'copyright', 'confidential', 'lab corp', 'quest'])
        )
        
        if is_header_footer:
            quarantined.append(line)
        else:
            body.append(line)
    
    return body, quarantined


def _extract_lines_pdfminer_basic(pdf_path: str) -> List[Dict]:
    """Extract lines using pdfminer with robust error handling"""
    laparams = LAParams(char_margin=2.0, line_margin=0.3, word_margin=0.1, all_texts=True)
    lines = []
    page_no = 0
    
    for layout in extract_pages(pdf_path, laparams=laparams):
        page_no += 1
        x0, y0, x1, y1 = getattr(layout, "bbox", (0, 0, 1, 1))
        h = max(y1 - y0, 1.0)
        
        for obj in getattr(layout, "_objs", []):
            if isinstance(obj, LTTextContainer):
                for line in getattr(obj, "_objs", []):
                    if isinstance(line, (LTTextLine, LTTextLineHorizontal)):
                        txt = (line.get_text() or "").strip()
                        if not txt:
                            continue
                            
                        bx0, by0, bx1, by1 = getattr(line, "bbox", (0, 0, 0, 0))
                        yMid = (by0 + by1) / 2.0
                        yNorm = 1.0 - (yMid / h)
                        
                        sizes = []
                        bold = False
                        for ch in getattr(line, "_objs", []):
                            if isinstance(ch, LTChar):
                                sizes.append(getattr(ch, "size", 0) or 0)
                                fn = str(getattr(ch, "fontname", "")).lower()
                                if "bold" in fn or "black" in fn or "heavy" in fn:
                                    bold = True
                        
                        fontSize = float(sum(sizes) / len(sizes)) if sizes else 0.0
                        
                        lines.append({
                            "page": page_no,
                            "text": txt,
                            "xLeft": float(bx0),
                            "xRight": float(bx1),
                            "yNorm": float(yNorm),
                            "fontSize": fontSize,
                            "isBold": bool(bold),
                            "hasText": True
                        })
    
    return lines


class PDFExtractor:
    """Extract structured text data from PDFs using pdfminer.six"""
    
    def __init__(
        self,
        dpi: int = 300,
        ocr_dpi: int | None = None,
        tesseract_lang: str = "eng",
        ocr_threshold: int = 25,
        use_ocr_on_text_light_pages: bool = False,
        force_ocr: bool = False,
        min_text_threshold: float | None = None,  # Legacy parameter
        **kwargs,
    ):
        """
        dpi:          used when rasterizing pages for OCR.
        ocr_dpi:      overrides dpi for OCR if provided.
        tesseract_lang: language(s) passed to tesseract (e.g. "eng").
        ocr_threshold: if a page has fewer than this many glyphs/characters,
                       treat as low-text and OCR it.
        use_ocr_on_text_light_pages: if True, OCR even pages with some text to improve accuracy.
        force_ocr:    if True, always attempt OCR regardless of text content.
        min_text_threshold: Legacy parameter, use ocr_threshold instead.
        kwargs:       ignored to be forward-compatible with worker configs.
        """
        self.dpi = dpi
        self.ocr_dpi = ocr_dpi
        self.tesseract_lang = tesseract_lang
        self.force_ocr = force_ocr
        
        # Handle legacy min_text_threshold parameter
        if min_text_threshold is not None:
            self.ocr_threshold = int(min_text_threshold)
            self.min_text_threshold = min_text_threshold
        else:
            self.ocr_threshold = ocr_threshold
            self.min_text_threshold = float(ocr_threshold)
        
        self.use_ocr_on_text_light_pages = use_ocr_on_text_light_pages
    
    def extract_lines(self, pdf_path: str) -> List[LineData]:
        """Extract all lines from PDF with OCR fallback for low-text pages and safety checks"""
        if not _ensure_pdf_imports():
            raise ImportError(f"PDF processing not available: {_pdf_error_msg}")
        return self._extract_with_safety_checks(pdf_path)

    def _extract_with_safety_checks(self, pdf_path: str) -> List[LineData]:
        """Extract PDF with char-count sanity gate and safe quarantine"""
        # Use robust pdfminer extraction
        raw = _extract_lines_pdfminer_basic(pdf_path)
        raw_chars = sum(len((l.get("text") or "").strip()) for l in raw)
        
        # Sanity gate: clearly readable PDF
        if raw_chars >= 20 and raw:
            safe, _hdr = _apply_header_quarantine_safely(raw)
            if safe:
                return [self._dict_to_linedata(line) for line in safe]
            # If quarantine emptied results, use original
            return [self._dict_to_linedata(line) for line in raw]
        
        # If low char count, try OCR
        ocr_lines = self._try_ocr_extraction(pdf_path)
        if ocr_lines:
            safe_ocr, _hdr = _apply_header_quarantine_safely(ocr_lines)
            if safe_ocr:
                return safe_ocr
            return ocr_lines
        
        # If both fail, write debug and raise
        self._write_debug_payload(pdf_path, raw, raw_chars)
        
        if not raw and not ocr_lines:
            raise ValueError(
                f"No text extracted from PDF after pdfminer+OCR: {pdf_path} "
                f"(raw_chars=0, ocr_chars=0)"
            )
        
        # Return whatever we have
        return [self._dict_to_linedata(line) for line in (raw or [])]
    
    def _dict_to_linedata(self, line_dict: Dict) -> LineData:
        """Convert dict to LineData object"""
        return LineData(
            page=line_dict.get('page', 1),
            text=line_dict.get('text', ''),
            xLeft=line_dict.get('xLeft', 0.0),
            xRight=line_dict.get('xRight', 0.0),
            yNorm=line_dict.get('yNorm', 0.0),
            fontSize=line_dict.get('fontSize', 12.0),
            isBold=line_dict.get('isBold', False),
            hasText=line_dict.get('hasText', True),
            source=line_dict.get('source', 'pdf')
        )
    
    def _try_ocr_extraction(self, pdf_path: str) -> List[Dict]:
        """Try OCR extraction as fallback"""
        if not self.force_ocr:
            # Skip OCR if not forced and dependencies aren't available
            return []
            
        if not _ensure_ocr_imports():
            if self.force_ocr:
                print(f"Warning: OCR was requested but not available: {_ocr_error_msg}")
            return []
        
        try:
            # Use existing OCR logic
            all_page_nums = set()
            temp_lines = self._extract_text_lines(pdf_path)
            if temp_lines:
                all_page_nums = set(temp_lines.keys())
            else:
                # If no pages detected, assume at least page 1
                all_page_nums = {1}
            
            ocr_lines_by_page = self._extract_ocr_lines(pdf_path, list(all_page_nums))
            
            # Flatten to single list
            ocr_lines = []
            for page_lines in ocr_lines_by_page.values():
                ocr_lines.extend([asdict(line) for line in page_lines])
            
            return ocr_lines
        except Exception:
            return []
    
    def _write_debug_payload(self, pdf_path: str, raw: List[Dict], raw_chars: int):
        """Write debug information when extraction fails"""
        try:
            Path("/data/outbox").mkdir(parents=True, exist_ok=True)
            debug_path = Path(f"/data/outbox/{Path(pdf_path).stem}.lines.debug.json")
            debug_data = {
                "raw_count": len(raw),
                "raw_chars": raw_chars,
                "first_lines": raw[:30],
            }
            debug_path.write_text(
                json.dumps(debug_data, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass  # Silent failure for debug output
    
    def extract_lines_legacy(self, pdf_path: str) -> List[LineData]:
        """Legacy extract method for backward compatibility"""
        all_lines = []
        
        # First pass: extract text with pdfminer
        text_lines_by_page = self._extract_text_lines(pdf_path)
        
        # Second pass: identify pages needing OCR
        pages_needing_ocr = self._identify_low_text_pages(text_lines_by_page)
        
        # If use_ocr_on_text_light_pages is enabled, also OCR pages with some text
        pages_to_ocr = pages_needing_ocr
        if self.use_ocr_on_text_light_pages:
            pages_to_ocr = list(text_lines_by_page.keys())
        
        # Third pass: OCR selected pages
        ocr_lines_by_page = {}
        if pages_to_ocr and (self.force_ocr or _ensure_ocr_imports()):
            if not _ensure_ocr_imports():
                print(f"Warning: OCR needed for low-text pages but not available: {_ocr_error_msg}")
            else:
                ocr_lines_by_page = self._extract_ocr_lines(pdf_path, pages_to_ocr)
        
        # Merge results
        all_page_nums = set(text_lines_by_page.keys()) | set(ocr_lines_by_page.keys())
        for page_num in sorted(all_page_nums):
            # Use OCR lines if page was identified as low-text, otherwise use PDF lines
            # But if use_ocr_on_text_light_pages is enabled, prefer OCR when available
            if page_num in pages_needing_ocr and page_num in ocr_lines_by_page:
                all_lines.extend(ocr_lines_by_page[page_num])
            elif self.use_ocr_on_text_light_pages and page_num in ocr_lines_by_page:
                all_lines.extend(ocr_lines_by_page[page_num])
            else:
                all_lines.extend(text_lines_by_page.get(page_num, []))
        
        return all_lines
    
    def extract_text(self, pdf_path: str) -> str:
        """Extract raw text from PDF"""
        lines = self.extract_lines(pdf_path)
        return '\n'.join(line.text.strip() for line in lines if line.text.strip())
    
    def _extract_text_lines(self, pdf_path: str) -> Dict[int, List[LineData]]:
        """Extract text lines using pdfminer.six"""
        lines_by_page = {}
        
        with open_filename(pdf_path, "rb") as fp:
            for page_num, page_layout in enumerate(extract_pages(fp), 1):
                lines = self._process_page_layout(page_layout, page_num)
                if lines:
                    lines_by_page[page_num] = lines
        
        return lines_by_page
    
    def _process_page_layout(self, page_layout: 'LTPage', page_num: int) -> List[LineData]:
        """Process a single page layout to extract line data"""
        lines = []
        page_height = page_layout.height
        
        def process_element(element):
            if isinstance(element, LTTextContainer):
                for child in element:
                    process_element(child)
            elif isinstance(element, LTTextLine):
                line_data = self._extract_line_data(element, page_num, page_height)
                if line_data:
                    lines.append(line_data)
            elif hasattr(element, '__iter__'):
                for child in element:
                    process_element(child)
        
        for element in page_layout:
            process_element(element)
        
        return lines
    
    def _extract_line_data(self, text_line: LTTextLine, page_num: int, page_height: float) -> Optional[LineData]:
        """Extract data from a single text line"""
        text = text_line.get_text().strip()
        if not text:
            return None
        
        # Get bounding box
        x0, y0, x1, y1 = text_line.bbox
        
        # Normalize y coordinate (0 at bottom, 1 at top)
        y_norm = y0 / page_height
        
        # Analyze font properties from characters
        font_size, is_bold = self._analyze_font_properties(text_line)
        
        return LineData(
            page=page_num,
            text=text,
            xLeft=x0,
            xRight=x1,
            yNorm=y_norm,
            fontSize=font_size,
            isBold=is_bold,
            hasText=len(text.strip()) > 0,
            source="pdf"
        )
    
    def _analyze_font_properties(self, text_line: LTTextLine) -> Tuple[float, bool]:
        """Analyze font size and bold status from line characters"""
        font_sizes = []
        bold_chars = 0
        total_chars = 0
        
        def collect_char_info(element):
            nonlocal font_sizes, bold_chars, total_chars
            if isinstance(element, LTChar):
                font_sizes.append(element.height)
                # Best-effort bold detection based on font name
                font_name = getattr(element, 'fontname', '').lower()
                if 'bold' in font_name or 'black' in font_name:
                    bold_chars += 1
                total_chars += 1
            elif hasattr(element, '__iter__'):
                for child in element:
                    collect_char_info(child)
        
        collect_char_info(text_line)
        
        # Calculate average font size
        avg_font_size = np.mean(font_sizes) if font_sizes else 12.0
        
        # Consider bold if >50% of characters are bold
        is_bold = (bold_chars / total_chars) > 0.5 if total_chars > 0 else False
        
        return float(avg_font_size), is_bold
    
    def _identify_low_text_pages(self, lines_by_page: Dict[int, List[LineData]]) -> List[int]:
        """Identify pages with minimal text content that need OCR"""
        low_text_pages = []
        
        for page_num, lines in lines_by_page.items():
            total_text_length = sum(len(line.text.strip()) for line in lines)
            if total_text_length < self.ocr_threshold:
                low_text_pages.append(page_num)
        
        # Also check for missing pages
        if lines_by_page:
            max_page = max(lines_by_page.keys())
            for page_num in range(1, max_page + 1):
                if page_num not in lines_by_page:
                    low_text_pages.append(page_num)
        
        return sorted(set(low_text_pages))
    
    def _extract_ocr_lines(self, pdf_path: str, page_numbers: List[int]) -> Dict[int, List[LineData]]:
        """Extract lines from specified pages using OCR"""
        if not _ensure_ocr_imports():
            print(f"Warning: OCR requested but not available: {_ocr_error_msg}")
            return {}
            
        ocr_lines_by_page = {}
        
        try:
            # Convert specific pages to images
            effective_dpi = self.ocr_dpi or self.dpi
            images = pdf2image(
                pdf_path,
                first_page=min(page_numbers),
                last_page=max(page_numbers),
                dpi=effective_dpi
            )
            
            # Map images to page numbers (convert_from_path is 1-indexed)
            page_to_image = {}
            for i, page_num in enumerate(range(min(page_numbers), max(page_numbers) + 1)):
                if page_num in page_numbers and i < len(images):
                    page_to_image[page_num] = images[i]
            
            # Process each image with OCR
            for page_num, image in page_to_image.items():
                lines = self._ocr_image_to_lines(image, page_num)
                if lines:
                    ocr_lines_by_page[page_num] = lines
        
        except Exception as e:
            print(f"OCR extraction failed for {pdf_path}: {e}")
        
        return ocr_lines_by_page
    
    def _ocr_image_to_lines(self, image: Image.Image, page_num: int) -> List[LineData]:
        """Extract lines from image using Tesseract OCR"""
        lines = []
        
        try:
            # Get detailed OCR data
            tesseract_config = f'--psm 6 -l {self.tesseract_lang}'
            ocr_data = pytesseract.image_to_data(
                image,
                output_type=pytesseract.Output.DICT,
                config=tesseract_config
            )
            
            # Group text by lines (same block_num, par_num, line_num)
            line_groups = {}
            image_height = image.height
            
            for i in range(len(ocr_data['text'])):
                if int(ocr_data['conf'][i]) < 30:  # Skip low confidence text
                    continue
                
                text = ocr_data['text'][i].strip()
                if not text:
                    continue
                
                line_key = (
                    ocr_data['block_num'][i],
                    ocr_data['par_num'][i],
                    ocr_data['line_num'][i]
                )
                
                if line_key not in line_groups:
                    line_groups[line_key] = {
                        'texts': [],
                        'x_coords': [],
                        'y_coords': [],
                        'widths': [],
                        'heights': [],
                        'confs': []
                    }
                
                line_groups[line_key]['texts'].append(text)
                line_groups[line_key]['x_coords'].append(ocr_data['left'][i])
                line_groups[line_key]['y_coords'].append(ocr_data['top'][i])
                line_groups[line_key]['widths'].append(ocr_data['width'][i])
                line_groups[line_key]['heights'].append(ocr_data['height'][i])
                line_groups[line_key]['confs'].append(ocr_data['conf'][i])
            
            # Convert line groups to LineData objects
            for line_group in line_groups.values():
                if not line_group['texts']:
                    continue
                
                # Combine text from all words in the line
                combined_text = ' '.join(line_group['texts'])
                
                # Calculate line bounding box
                x_left = min(line_group['x_coords'])
                x_rights = [x + w for x, w in zip(line_group['x_coords'], line_group['widths'])]
                x_right = max(x_rights)
                
                y_top = min(line_group['y_coords'])
                # Normalize y coordinate (flip since OCR uses top-down, we want bottom-up)
                y_norm = 1.0 - (y_top / image_height)
                
                # Estimate font size from OCR height
                avg_height = np.mean(line_group['heights'])
                font_size = float(avg_height * 0.75)  # Rough conversion from pixel height to point size
                
                # No reliable bold detection from OCR
                is_bold = False
                
                line_data = LineData(
                    page=page_num,
                    text=combined_text,
                    xLeft=float(x_left),
                    xRight=float(x_right),
                    yNorm=y_norm,
                    fontSize=font_size,
                    isBold=is_bold,
                    hasText=True,
                    source="ocr"
                )
                
                lines.append(line_data)
        
        except Exception as e:
            print(f"OCR processing failed for page {page_num}: {e}")
        
        return lines