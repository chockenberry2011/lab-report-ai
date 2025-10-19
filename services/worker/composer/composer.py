"""
Panel composer for structuring lab data into coherent panels
"""

import time
import re
import uuid
import logging
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
import math
from statistics import median

from .schemas import Panel, TestRow, ComposerResult
from .panel_headers import score_panel_header
from .scoring import LabDataScorer

logger = logging.getLogger(__name__)


def is_probably_test_row(text: str) -> bool:
    """
    Validate if text is probably a test row to prevent header/envelope lines 
    from being treated as TEST_ROW.
    
    Requirements:
    - Must have a numeric value token shortly after a plausible test name
    - Prefer a recognized unit from medical unit allow-list
    - Reject header patterns (Specimen ID:, Accession, MRN, etc.)
    - Reject phone/CLIA/NPI patterns or multiple colon labels
    
    Args:
        text: Line text to validate
        
    Returns:
        bool: True if text is probably a test row
    """
    if not text or not text.strip():
        return False
    
    text = text.strip()
    
    # Header patterns to reject
    header_patterns = [
        r'specimen\s+id\s*:',
        r'accession\s*:?',
        r'acct\s*#',
        r'mrn\s*:?',
        r'patient\s+id\s*:?',
        r'phone\s*:?',
        r'fax\s*:?',
        r'rte\s*:?',
        r'clia\s*:?',
        r'npi\s*:?',
        r'director\s*:?',
        r'location\s*:?',
        r'collected\s*:?',
        r'received\s*:?',
        r'entered\s*:?',
        r'reported\s*:?'
    ]
    
    # Check for header patterns
    for pattern in header_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    # Check for phone number patterns (xxx-xxx-xxxx or (xxx) xxx-xxxx)
    phone_pattern = r'(\(\d{3}\)\s*\d{3}-\d{4}|\d{3}-\d{3}-\d{4})'
    if re.search(phone_pattern, text):
        return False
    
    # Check for CLIA pattern (like "CLIA # 05D0123456")
    clia_pattern = r'clia\s*#?\s*\d{2}[a-z]\d{7}'
    if re.search(clia_pattern, text, re.IGNORECASE):
        return False
    
    # Check for NPI pattern (10 digits)
    npi_pattern = r'npi\s*:?\s*\d{10}'
    if re.search(npi_pattern, text, re.IGNORECASE):
        return False
    
    # Check for multiple colon labels (e.g., "Name: John Doe, DOB: 1990-01-01")
    colon_count = text.count(':')
    if colon_count >= 2:
        return False
    
    # Extract tokens
    tokens = text.split()
    if len(tokens) < 2:
        return False
    
    # Look for numeric value
    has_numeric = False
    numeric_position = -1
    for i, token in enumerate(tokens):
        # Check for numeric patterns: digits possibly with decimal, comparators
        if re.search(r'[<>]?\d+\.?\d*', token):
            has_numeric = True
            numeric_position = i
            break
    
    if not has_numeric:
        return False
    
    # Medical unit allow-list (comprehensive set)
    medical_units = {
        # Concentration units
        'mg/dL', 'g/dL', 'g/L', 'mg/L', 'mcg/dL', 'mcg/L', 'ng/mL', 'pg/mL',
        'mmol/L', 'umol/L', 'nmol/L', 'pmol/L', 'mEq/L', 'IU/L', 'U/L',
        'mU/L', 'uU/mL', 'mIU/L', 'uIU/mL', 'mL/min/1.73',
        # Blood count units
        'K/uL', 'M/uL', 'cells/uL', '10^3/uL', '10^6/uL', '10^9/L',
        'x10^3/uL', 'x10^6/uL', 'thou/uL', 'mill/uL',
        # Common units
        '%', 'percent', 'ratio', 'index', 'score', 'units',
        # Time units
        'sec', 'seconds', 'min', 'minutes', 'hr', 'hours', 'day', 'days',
        # Pressure units
        'mmHg', 'cmH2O', 'kPa',
        # Temperature units
        'C', '°C', 'F', '°F',
        # Volume units
        'mL', 'L', 'uL', 'dL',
        # Mass units
        'g', 'kg', 'mg', 'ug', 'ng', 'pg',
        # Activity units
        'IU', 'U', 'mU', 'uU', 'KU', 'MU',
        # Other medical units
        'fL', 'per hpf', 'copies/mL', 'cells/mL', 'cm', 'mm', 'bpm'
    }
    
    # Look for medical units in the text
    has_medical_unit = False
    for token in tokens:
        # Clean token of punctuation for matching
        clean_token = re.sub(r'[^\w/\^\.\-]', '', token)
        if clean_token in medical_units:
            has_medical_unit = True
            break
    
    # Primary requirement: Must have a medical unit for high confidence
    # But still validate basic structure even with medical units
    if has_medical_unit:
        # Even with medical units, apply basic structure validation
        first_token = tokens[0]
        
        # Reject obvious non-test patterns even if they have medical units
        if (first_token.lower() in ['the', 'and', 'or', 'in', 'on', 'at', 'to', 'for'] or
            first_token.endswith(':') or
            re.match(r'^\d+$', first_token) or  # Pure number as first token
            numeric_position > 5):  # Numeric too far from start
            return False
        
        return True
    
    # If no medical unit, apply very strict validation
    # Only accept if it looks like a simple medical measurement
    if numeric_position <= 1:  # Numeric must be in first 2 positions (test_name + value)
        first_token = tokens[0]
        
        # Reject obvious non-test patterns
        if (first_token.lower() in ['the', 'and', 'or', 'in', 'on', 'at', 'to', 'for', 'page', 'total', 'section', 'reference', 'distance', 'price'] or
            first_token.endswith(':') or
            re.match(r'^\d+$', first_token)):  # Pure number as first token
            return False
        
        # Additional validation for common medical test name patterns
        medical_test_patterns = [
            r'(?i)^(glucose|cholesterol|triglyceride|sodium|potassium|chloride|co2|bun|creatinine)$',
            r'(?i)^(hemoglobin|hematocrit|wbc|rbc|platelet|mcv|mch|mchc)$', 
            r'(?i)^(tsh|t4|t3|cortisol|insulin|hba1c|psa|cea)$',
            r'(?i)^(alt|ast|alp|ggt|ldh|ck|troponin|bnp|procalcitonin)$',
            r'(?i)^(temperature|weight|height|age|bp|pulse|resp)$'
        ]
        
        # Check if first token matches common medical test names
        for pattern in medical_test_patterns:
            if re.match(pattern, first_token):
                return True
        
        # If no medical unit and no recognized test name, reject
        return False
    
    return False


def stitch_testrow_candidates(lines, y_tol=0.006, gap_tol=28):
    """
    Input: consecutive lines around a candidate row (same page).
    If we see a pattern like:
        [ '152.222 H' ] [ 'uIU/mL' ] [ '0.450 - 4.500' ] [ 'TSH' ]
    or any permutation near the same y (within y_tol) and small x gaps (< gap_tol),
    merge to a single logical row. Heuristics:
      - TEST_NAME: leftmost text span without digits, prefer alpha tokens.
      - VALUE: first numeric token (int/float) possibly with sign.
      - UNIT: next short token from a whitelist (mg/dL, uIU/mL, IU/L, g/dL, %, etc).
      - REF_RANGE: token containing "x - y" or "low–high", tolerate unicode dashes.
      - FLAG: tokens in {H, L, High, Low, A, Abn}.
    Return a dict with extracted fields + spans used, and a confidence score combining regex hits + proximity.
    """
    if not lines:
        return None
    
    # Unit whitelist for recognition
    UNIT_WHITELIST = {
        'mg/dL', 'g/dL', 'mEq/L', 'mmol/L', 'uIU/mL', 'IU/L', 'ng/mL', 'pg/mL',
        'mcg/dL', 'ug/dL', 'mg/L', 'g/L', '%', 'ratio', 'index', 'units/L',
        'U/L', 'mU/L', 'fL', 'pg', 'K/uL', 'M/uL', 'cells/uL', 'per hpf',
        'copies/mL', 'cells/mL', 'mg', 'g', 'mL', 'L', 'cm', 'mm', 'bpm'
    }
    
    # Flag patterns
    FLAG_PATTERNS = {'H', 'L', 'High', 'Low', 'A', 'Abn', 'CRITICAL', 'PANIC', '*'}
    
    # Group lines by proximity (same y within tolerance)
    if len(lines) == 1:
        candidate_groups = [lines]
    else:
        candidate_groups = []
        current_group = [lines[0]]
        
        for line in lines[1:]:
            prev_y = current_group[-1].get('y_norm', current_group[-1].get('yNorm', 0))
            curr_y = line.get('y_norm', line.get('yNorm', 0))
            
            if abs(curr_y - prev_y) <= y_tol:
                current_group.append(line)
            else:
                if current_group:
                    candidate_groups.append(current_group)
                current_group = [line]
        
        if current_group:
            candidate_groups.append(current_group)
    
    best_result = None
    best_confidence = 0.0
    
    for group in candidate_groups:
        if len(group) < 2:  # Need at least 2 fragments to stitch
            continue
            
        # Sort by x position (left to right)
        sorted_group = sorted(group, key=lambda x: x.get('x_left', x.get('xLeft', 0)))
        
        # Check x-proximity (gaps should be reasonable)
        valid_group = True
        for i in range(len(sorted_group) - 1):
            curr_right = sorted_group[i].get('x_right', sorted_group[i].get('xRight', 0))
            next_left = sorted_group[i + 1].get('x_left', sorted_group[i + 1].get('xLeft', 0))
            gap = next_left - curr_right
            if gap > gap_tol:
                valid_group = False
                break
        
        if not valid_group:
            continue
        
        # Extract text from each fragment
        fragments = []
        for line in sorted_group:
            text = line.get('text', '').strip()
            if text:
                fragments.append({
                    'text': text,
                    'x_left': line.get('x_left', line.get('xLeft', 0)),
                    'x_right': line.get('x_right', line.get('xRight', 0)),
                    'line_data': line
                })
        
        if len(fragments) < 2:
            continue
        
        # Apply heuristics to extract fields
        result = _extract_testrow_fields(fragments)
        
        if result and result['confidence'] > best_confidence:
            result['used_fragments'] = fragments
            result['source_lines'] = sorted_group
            best_result = result
            best_confidence = result['confidence']
    
    return best_result


def _extract_testrow_fields(fragments):
    """Extract test row fields from text fragments using heuristics"""
    
    # Initialize result
    result = {
        'test_name': None,
        'result_value': None, 
        'units': None,
        'reference_range': None,
        'flag': None,
        'confidence': 0.0,
        'field_spans': {}
    }
    
    confidence = 0.0
    used_fragments = set()
    
    # Unit whitelist for recognition
    UNIT_WHITELIST = {
        'mg/dL', 'g/dL', 'mEq/L', 'mmol/L', 'uIU/mL', 'IU/L', 'ng/mL', 'pg/mL',
        'mcg/dL', 'ug/dL', 'mg/L', 'g/L', '%', 'ratio', 'index', 'units/L',
        'U/L', 'mU/L', 'fL', 'pg', 'K/uL', 'M/uL', 'cells/uL', 'per hpf',
        'copies/mL', 'cells/mL', 'mg', 'g', 'mL', 'L', 'cm', 'mm', 'bpm'
    }
    
    # Flag patterns
    FLAG_PATTERNS = {'H', 'L', 'High', 'Low', 'A', 'Abn', 'CRITICAL', 'PANIC', '*'}
    
    # 1. Look for VALUE: numeric patterns
    value_pattern = re.compile(r'^[<>≤≥]?\s*(\d+\.?\d*)\s*([HL*]?)$')
    for i, frag in enumerate(fragments):
        match = value_pattern.match(frag['text'])
        if match and i not in used_fragments:
            result['result_value'] = match.group(1)
            confidence += 0.2
            used_fragments.add(i)
            result['field_spans']['result_value'] = (frag['x_left'], frag['x_right'])
            
            # Check for flag in same fragment
            flag_part = match.group(2)
            if flag_part and flag_part in FLAG_PATTERNS:
                result['flag'] = flag_part
                confidence += 0.1
                result['field_spans']['flag'] = (frag['x_left'], frag['x_right'])
            break
    
    # 2. Look for UNIT: match against whitelist
    for i, frag in enumerate(fragments):
        if i in used_fragments:
            continue
        text = frag['text'].strip()
        if text in UNIT_WHITELIST:
            result['units'] = text
            confidence += 0.2
            used_fragments.add(i)
            result['field_spans']['units'] = (frag['x_left'], frag['x_right'])
            break
    
    # 3. Look for REFERENCE_RANGE: contains dash patterns
    range_pattern = re.compile(r'(\d+\.?\d*)\s*[-–—]\s*(\d+\.?\d*)')
    for i, frag in enumerate(fragments):
        if i in used_fragments:
            continue
        if range_pattern.search(frag['text']):
            result['reference_range'] = frag['text']
            confidence += 0.2
            used_fragments.add(i)
            result['field_spans']['reference_range'] = (frag['x_left'], frag['x_right'])
            break
    
    # 4. Look for FLAG: standalone flag tokens
    if not result['flag']:
        for i, frag in enumerate(fragments):
            if i in used_fragments:
                continue
            text = frag['text'].strip()
            if text in FLAG_PATTERNS:
                result['flag'] = text
                confidence += 0.1
                used_fragments.add(i)
                result['field_spans']['flag'] = (frag['x_left'], frag['x_right'])
                break
    
    # 5. Look for TEST_NAME: leftmost unused fragment, prefer alpha
    unused_fragments = [(i, frag) for i, frag in enumerate(fragments) if i not in used_fragments]
    if unused_fragments:
        # Sort by x position, prefer leftmost
        unused_fragments.sort(key=lambda x: x[1]['x_left'])
        
        # Prefer fragments with alpha characters and no digits
        alpha_frags = [(i, frag) for i, frag in unused_fragments 
                      if re.search(r'[a-zA-Z]', frag['text']) and not re.search(r'\d', frag['text'])]
        
        if alpha_frags:
            i, frag = alpha_frags[0]
            result['test_name'] = frag['text']
            used_fragments.add(i)
            result['field_spans']['test_name'] = (frag['x_left'], frag['x_right'])
        elif unused_fragments:
            # Fallback to leftmost unused
            i, frag = unused_fragments[0]
            result['test_name'] = frag['text']  
            used_fragments.add(i)
            result['field_spans']['test_name'] = (frag['x_left'], frag['x_right'])
    
    # 6. Proximity bonus: close fragments get higher confidence
    if len(used_fragments) >= 2:
        # Calculate average gap between used fragments
        used_frags = [fragments[i] for i in sorted(used_fragments)]
        gaps = []
        for i in range(len(used_frags) - 1):
            gap = used_frags[i + 1]['x_left'] - used_frags[i]['x_right']
            gaps.append(gap)
        
        if gaps:
            avg_gap = sum(gaps) / len(gaps)
            # Bonus for small gaps (good proximity)
            if avg_gap <= 28:
                confidence += 0.3
            elif avg_gap <= 50:
                confidence += 0.2
            elif avg_gap <= 100:
                confidence += 0.1
    
    result['confidence'] = min(confidence, 1.0)  # Cap at 1.0
    
    # Only return if we got meaningful fields
    if result['result_value'] or result['test_name']:
        return result
    
    return None


@dataclass
class LineContext:
    """Context information for a line during processing"""
    text: str
    role: str
    page: int
    line_number: int
    y_norm: float
    x_left: float
    x_right: float
    font_size: float
    is_bold: bool
    in_quarantine: bool = False


def extract_codes_from_vicinity(target_line: Dict, all_lines: List[Dict], y_tolerance: float = 0.01, x_search_radius: int = 200) -> Dict[str, str]:
    """
    Extract LOINC/CPT codes from the vicinity of a target line (panel header or test row)
    
    Args:
        target_line: The line to search around
        all_lines: All available lines to search through
        y_tolerance: Y-coordinate tolerance for considering lines in vicinity
        x_search_radius: X-coordinate search radius in normalized units
        
    Returns:
        Dict with extracted codes: {'loinc': 'xxx', 'cpt': 'yyy'}
    """
    # NEW: Extract codes using robust regex patterns
    codes = {}
    target_page = target_line.get('page', 1)
    target_y = target_line.get('yNorm', target_line.get('y_norm', 0.0))
    target_x = target_line.get('xLeft', target_line.get('x_left', 0.0))
    
    # Search in vicinity - same page, similar y-coordinate
    vicinity_lines = []
    for line in all_lines:
        if line.get('page', 1) != target_page:
            continue
        line_y = line.get('yNorm', line.get('y_norm', 0.0))
        line_x = line.get('xLeft', line.get('x_left', 0.0))
        
        # Check if in y-band vicinity
        if abs(line_y - target_y) <= y_tolerance:
            # Prefer rightmost codes (often at end of line)
            distance = abs(line_x - target_x)
            vicinity_lines.append((distance, line))
    
    # Sort by distance, prioritize closer/rightmost
    vicinity_lines.sort(key=lambda x: x[0])
    
    # Extract codes using regex
    code_pattern = re.compile(r'\b(LOINC|CPT)\s*[:#]?\s*([A-Z0-9-]+)\b', re.IGNORECASE)
    
    for distance, line in vicinity_lines:
        text = line.get('text', '')
        matches = code_pattern.findall(text)
        
        for code_type, code_value in matches:
            code_key = code_type.lower()
            if code_key not in codes:  # Take first occurrence
                codes[code_key] = code_value
    
    return codes


def extract_panel_comments(panel_header_line: Dict, all_lines: List[Dict], max_search_lines: int = 10) -> Optional[str]:
    """
    Extract panel-level comments by looking for footnotes and references
    
    Args:
        panel_header_line: The panel header line
        all_lines: All available lines
        max_search_lines: Maximum number of lines to search after panel header
        
    Returns:
        Concatenated comments if found
    """
    # NEW: Extract panel comments from footnotes and references
    comments = []
    panel_page = panel_header_line.get('page', 1)
    header_line_num = panel_header_line.get('line_number', 0)
    
    # Look for footnote markers in panel header
    header_text = panel_header_line.get('text', '')
    footnote_markers = re.findall(r'[*†‡§¶#]|\[\d+\]|\(\d+\)', header_text)
    
    if not footnote_markers:
        return None
    
    # Search for corresponding footnotes in subsequent lines
    search_start = header_line_num + 1
    search_end = min(len(all_lines), search_start + max_search_lines)
    
    for i in range(search_start, search_end):
        if i >= len(all_lines):
            break
        line = all_lines[i]
        
        # Skip if different page
        if line.get('page', 1) != panel_page:
            continue
        
        text = line.get('text', '')
        
        # Look for footnote references
        for marker in footnote_markers:
            # Clean marker for regex (escape special chars)
            escaped_marker = re.escape(marker)
            pattern = f'^{escaped_marker}\\s*(.+)'
            match = re.search(pattern, text.strip())
            if match:
                comments.append(match.group(1).strip())
    
    # Also look for bottom-of-page footnotes
    page_lines = [line for line in all_lines if line.get('page', 1) == panel_page]
    if page_lines:
        # Check last 5 lines of page for footnotes
        for line in page_lines[-5:]:
            text = line.get('text', '')
            for marker in footnote_markers:
                escaped_marker = re.escape(marker)
                pattern = f'^{escaped_marker}\\s*(.+)'
                match = re.search(pattern, text.strip())
                if match and match.group(1).strip() not in comments:
                    comments.append(match.group(1).strip())
    
    return '; '.join(comments) if comments else None


def enhance_test_row_with_bio_tags(test_row: TestRow, line: Dict, all_lines: List[Dict]) -> TestRow:
    """
    Enhance test row with additional BIO tags and fallback extraction
    
    Args:
        test_row: Existing TestRow object
        line: The source line dict
        all_lines: All lines for vicinity search
        
    Returns:
        Enhanced TestRow with additional fields
    """
    # NEW: Enhanced test row extraction with BIO tags and fallbacks
    text = line.get('text', '')
    
    # Extract codes from vicinity if not already present
    if not test_row.codes:
        codes = extract_codes_from_vicinity(line, all_lines)
        if codes:
            test_row.codes = codes
    
    # Extract methodology using keywords
    if not test_row.methodology:
        method_patterns = [
            r'(?:Method|Methodology)[\s:]*([^,\n]+)',
            r'\b(Immunoassay|LC/MS-MS|LC-MS|HPLC|RIA|ELISA|PCR|Flow Cytometry|Microscopy)\b'
        ]
        for pattern in method_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                test_row.methodology = match.group(1).strip()
                break
    
    # Extract observation time
    if not test_row.observed_at:
        time_patterns = [
            r'\b(\d{1,2}:\d{2}\s*(?:AM|PM))\b',  # 12-hour format
            r'\b(\d{1,2}:\d{2})\b'  # 24-hour format
        ]
        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                test_row.observed_at = match.group(1)
                break
    
    # Extract comments/notes - look for remaining text after main fields
    if not test_row.comments:
        # Simple heuristic: text after known patterns might be comments
        comment_text = text
        
        # Remove known field patterns
        if test_row.test_name:
            comment_text = comment_text.replace(test_row.test_name, '').strip()
        if test_row.result_value:
            comment_text = comment_text.replace(str(test_row.result_value), '').strip()
        if test_row.units:
            comment_text = comment_text.replace(test_row.units, '').strip()
        if test_row.reference_range:
            comment_text = comment_text.replace(test_row.reference_range, '').strip()
        if test_row.flag:
            comment_text = comment_text.replace(test_row.flag, '').strip()
        
        # Clean up and check if meaningful comment remains
        comment_text = re.sub(r'[^\w\s]', ' ', comment_text).strip()
        if len(comment_text) > 5 and not re.match(r'^\d+\.?\d*$', comment_text):
            test_row.comments = comment_text
    
    return test_row


class PanelComposer:
    """
    Composer that walks lines top-down and maintains panel state
    """
    
    def __init__(self, 
                 page_break_lookahead: int = 8,
                 min_continuity_score: float = 0.3,
                 cost_weight_switches: float = 2.0,
                 cost_weight_coherence: float = 1.0,
                 enable_scoring: bool = True,
                 scoring_config: Optional[Dict] = None,
                 header_strong_threshold: float = 0.6):
        """
        Initialize the composer
        
        Args:
            page_break_lookahead: Number of lines to look ahead after page break
            min_continuity_score: Minimum score to continue a panel across pages
            cost_weight_switches: Weight for panel switch penalty in cost function
            cost_weight_coherence: Weight for coherence bonus in cost function
            enable_scoring: Whether to enable comprehensive scoring
            scoring_config: Configuration dict for scorer
        """
        self.page_break_lookahead = page_break_lookahead
        self.min_continuity_score = min_continuity_score
        self.cost_weight_switches = cost_weight_switches
        self.cost_weight_coherence = cost_weight_coherence
        self.enable_scoring = enable_scoring
        self.header_strong_threshold = header_strong_threshold
        
        # Initialize scorer if enabled
        if enable_scoring:
            scoring_config = scoring_config or {}
            self.scorer = LabDataScorer(**scoring_config)
        else:
            self.scorer = None
        
        # State tracking
        self.current_panel: Optional[Panel] = None
        self.panels: List[Panel] = []
        self.page_breaks_handled = 0
        self.repairs_made = 0
        self.panels_seen: List[Dict] = []  # Track panel headers for debugging
        
        # Fallback detection parameters (K within M)
        self._fallback_K = 3
        self._fallback_M = 5
        
        # Flag controlling whether to continue an open panel after a page break
        self._continue_panel_on_next_page: bool = True
        
        # Panel grouping tracking
        self.paneling_metadata = {
            'opened_synthetic': False,
            'repaired_at_page': None
        }
        
        # Patterns for test row parsing
        self.test_patterns = {
            'numeric_result': re.compile(r'^(.+?)\s+([\d.,]+)\s*([a-zA-Z/%]+)?\s*(.*)$'),
            'text_result': re.compile(r'^(.+?)\s+(NEGATIVE|POSITIVE|NORMAL|ABNORMAL|HIGH|LOW)\s*(.*)$'),
            'range_pattern': re.compile(r'([\d.,]+)\s*-\s*([\d.,]+)'),
            'flag_pattern': re.compile(r'\b(HIGH|LOW|CRITICAL|ABNORMAL|H|L|C|A)\b', re.IGNORECASE)
        }
        # Simple entire-cell reference range pattern for column repair
        self._simple_ref_range_line_re = re.compile(r'^\s*[<>]?\d+(\.\d+)?\s*[-–]\s*[<>]?\d+(\.\d+)?\s*$', re.UNICODE)
        # Cache for per-page anchors
        self._page_unit_anchor: Dict[int, Optional[float]] = {}
        self._page_ref_anchor: Dict[int, Optional[float]] = {}
    
    def compose(self, lines_data: List[Dict], classifier_probabilities: Optional[Dict[int, float]] = None) -> ComposerResult:
        """
        Main composition method
        
        Args:
            lines_data: List of line dictionaries with text, role, page, etc.
            classifier_probabilities: Optional dict mapping line numbers to role classification probabilities
            
        Returns:
            ComposerResult with structured panels and scoring information
        """
        start_time = time.time()
        
        # NEW: Store lines_data for enhanced extraction
        self._lines_data = lines_data
        
        # Convert to LineContext objects
        line_contexts = self._prepare_line_contexts(lines_data)
        
        # Store line contexts for stitching access
        self._current_line_contexts = line_contexts
        
        # First pass: walk lines and build panels
        processed_lines = self._first_pass(line_contexts)
        
        # Second pass: repair page-break attachments
        self._second_pass(processed_lines)
        
        # Third pass: continuity repair for synthetic panels
        self._third_pass_continuity_repair(processed_lines)
        
        # Close any open panels
        if self.current_panel and self.current_panel.open:
            self.current_panel.close_panel()
        
        # Fourth pass: repair split rows (stitch value/unit/ref_range across lines)
        self._repair_split_rows(self.panels)
        
        # Safe fallback: create Unknown panels if no panels but TEST_ROW lines exist
        test_row_contexts = [ctx for ctx in line_contexts if ctx.role == 'TEST_ROW']
        if not self.panels and test_row_contexts:
            self._create_unknown_panels(test_row_contexts)
        
        # Filter panels by confidence threshold (lowered from default)
        min_confidence_threshold = 0.25  # Lowered threshold
        filtered_panels = []
        
        for panel in self.panels:
            if len(panel.test_rows) > 0 and panel.continuity_score >= min_confidence_threshold:
                # Flag for review if confidence is low
                if panel.continuity_score < 0.5:
                    panel.needs_review = True
                    if not hasattr(panel, 'review_reasons'):
                        panel.review_reasons = []
                    panel.review_reasons.append("weak_panel_header")
                
                filtered_panels.append(panel)
        
        self.panels = filtered_panels
        
        processing_time = time.time() - start_time
        
        # Create initial result
        result = ComposerResult(
            panels=self.panels,
            total_lines_processed=len(lines_data),
            total_test_rows=sum(len(panel.test_rows) for panel in self.panels),
            page_breaks_handled=self.page_breaks_handled,
            repairs_made=self.repairs_made,
            processing_time=processing_time
        )
        
        # Store panels_seen for debugging
        result.panels_seen = self.panels_seen
        
        # Store paneling metadata for debugging
        result.paneling = self.paneling_metadata
        
        # Apply scoring if enabled
        if self.enable_scoring and self.scorer:
            self._apply_scoring(result, classifier_probabilities)
        
        # Run validation self-check
        self._validate_composition(result)
        
        return result
    
    def _prepare_line_contexts(self, lines_data: List[Dict]) -> List[LineContext]:
        """Convert raw line data to LineContext objects"""
        contexts = []
        
        for i, line_data in enumerate(lines_data):
            # Handle both extractor format and role classifier format
            text = line_data.get('text', '')
            # Accept role from line["role"] (primary), fallback to predicted_role
            role = line_data.get('role') or line_data.get('predicted_role', 'UNKNOWN')
            # Normalize roles for composer logic
            if role == 'OTHER':
                role = 'JUNK'
            
            # Check for quarantine zones
            in_quarantine = self._is_in_quarantine(text, role)
            
            context = LineContext(
                text=text,
                role=role,
                page=line_data.get('page', 1),
                line_number=i,
                y_norm=line_data.get('yNorm', line_data.get('y_norm', 0.0)),
                x_left=line_data.get('xLeft', line_data.get('x_left', 0.0)),
                x_right=line_data.get('xRight', line_data.get('x_right', 0.0)),
                font_size=line_data.get('fontSize', line_data.get('font_size', 12.0)),
                is_bold=line_data.get('isBold', line_data.get('is_bold', False)),
                in_quarantine=in_quarantine
            )
            contexts.append(context)
        
        return contexts
    
    def _is_in_quarantine(self, text: str, role: str) -> bool:
        """Check if line is in quarantine zone (headers/footers)"""
        return role in ['PAGE_HEADER', 'PAGE_FOOTER'] or 'PAGE_HEADER' in text or 'PAGE_FOOTER' in text
    
    def _first_pass(self, line_contexts: List[LineContext]) -> List[LineContext]:
        """First pass: walk lines top-down and maintain panel state"""
        processed_lines = []
        current_page = 1
        test_row_buffer = []  # Buffer for orphaned test rows
        
        for i, context in enumerate(line_contexts):
            # Skip quarantine zones
            if context.in_quarantine:
                processed_lines.append(context)
                continue
            
            # Handle page breaks
            if context.page > current_page:
                self._handle_page_break(line_contexts, i)
                current_page = context.page
            
            # Process line based on role
            if context.role == 'SECTION_PANEL':
                self._open_new_panel(context)
                # Process any buffered test rows under new panel
                self._process_buffered_test_rows(test_row_buffer)
                test_row_buffer = []
            else:
                # Panel-opening safety net: conservative fallback for opening a panel
                text = (context.text or "").strip()
                is_strong = bool(context.is_bold or context.font_size >= 10)
                looks_like_panel = is_strong and ("panel" in text.lower() or bool(re.search(r'(?i)\bpanel\b|\bpanel\s*\(', text)))
                
                if not (self.current_panel and self.current_panel.open) and context.role != 'SECTION_PANEL' and looks_like_panel:
                    # Open a new panel with fallback source
                    self._open_new_panel_fallback(context)
                    # Process any buffered test rows under new panel
                    self._process_buffered_test_rows(test_row_buffer)
                    test_row_buffer = []
                
            if context.role == 'TEST_ROW':
                # Guardrail: Validate if this is probably a test row
                if not is_probably_test_row(context.text):
                    # Re-role to HEADER_FIELD and send to header/envelope extraction
                    logger.info(f"Re-roling TEST_ROW to HEADER_FIELD: '{context.text}' (line {context.line_number})")
                    context.role = 'HEADER_FIELD'
                    # Continue processing as HEADER_FIELD (will be handled by header extraction)
                else:
                    if self.current_panel and self.current_panel.open and self._continue_panel_on_next_page:
                        self._attach_test_row(context)
                    else:
                        # Buffer orphaned test rows
                        test_row_buffer.append(context)
                        # Check for synthetic panel opportunity
                        if not (self.current_panel and self.current_panel.open):
                            if self._should_open_synthetic_panel(test_row_buffer, context):
                                self._create_synthetic_panel(test_row_buffer, context)
                                test_row_buffer = []
                            # If no synthetic panel created, check K-in-M lookahead for fallback
                            elif self._should_open_fallback(line_contexts, i):
                                self._create_fallback_panel(test_row_buffer)
                                test_row_buffer = []
            
            processed_lines.append(context)
        
        # Process any remaining buffered test rows
        if test_row_buffer:
            self._process_buffered_test_rows(test_row_buffer)
        
        return processed_lines
    
    def _handle_page_break(self, line_contexts: List[LineContext], current_idx: int):
        """Handle page break logic with enhanced continuity heuristics"""
        self.page_breaks_handled += 1
        
        if not self.current_panel or not self.current_panel.open:
            return
        
        # Look ahead for new panel header within first P non-header/footer lines
        non_header_lines_seen = 0
        lookahead_end = min(current_idx + 20, len(line_contexts))  # Extended search window
        found_new_panel = False
        strong_header_found = False
        
        for j in range(current_idx, lookahead_end):
            context = line_contexts[j]
            # Skip header/footer lines
            if context.role in ['PAGE_HEADER', 'PAGE_FOOTER']:
                continue
            
            non_header_lines_seen += 1
            if context.role == 'SECTION_PANEL':
                found_new_panel = True
                # Only treat as a new panel if the header is strong enough
                header_score = score_panel_header({
                    'text': context.text,
                    'is_bold': context.is_bold,
                    'y_norm': context.y_norm,
                })
                if header_score >= self.header_strong_threshold:
                    strong_header_found = True
                    break
            
            # Stop after examining N=P non-header/footer lines
            if non_header_lines_seen >= self.page_break_lookahead:
                break
        
        # Continue panel by default unless a new header appears within P lines
        if found_new_panel and strong_header_found:
            # Close to avoid attaching early rows on next page to the old panel
            self.current_panel.close_panel()
            self.current_panel = None
            self._continue_panel_on_next_page = False
        else:
            self._continue_panel_on_next_page = True
    
    def _calculate_continuity_score(self, line_contexts: List[LineContext], page_break_idx: int) -> float:
        """Calculate continuity score across page break"""
        if not self.current_panel or not self.current_panel.test_rows:
            return 0.0
        
        # Look at patterns before and after page break
        pre_break_patterns = self._extract_patterns_before(line_contexts, page_break_idx)
        post_break_patterns = self._extract_patterns_after(line_contexts, page_break_idx)
        
        # Calculate pattern similarity
        similarity = self._calculate_pattern_similarity(pre_break_patterns, post_break_patterns)
        
        # Factor in current panel coherence
        panel_coherence = self.current_panel.calculate_coherence_score()
        
        return (similarity + panel_coherence) / 2.0
    
    def _extract_patterns_before(self, line_contexts: List[LineContext], page_break_idx: int) -> Dict[str, int]:
        """Extract patterns from lines before page break"""
        patterns = {'has_units': 0, 'has_ranges': 0, 'numeric_results': 0}
        
        # Look at last few test rows before page break
        start_idx = max(0, page_break_idx - 5)
        for i in range(start_idx, page_break_idx):
            if i < len(line_contexts) and line_contexts[i].role == 'TEST_ROW':
                text = line_contexts[i].text
                if re.search(r'\b(mg|g|L|mL|%|mmol|units)\b', text):
                    patterns['has_units'] += 1
                if re.search(r'\d+\s*-\s*\d+', text):
                    patterns['has_ranges'] += 1
                if re.search(r'\b\d+\.?\d*\b', text):
                    patterns['numeric_results'] += 1
        
        return patterns
    
    def _extract_patterns_after(self, line_contexts: List[LineContext], page_break_idx: int) -> Dict[str, int]:
        """Extract patterns from lines after page break"""
        patterns = {'has_units': 0, 'has_ranges': 0, 'numeric_results': 0}
        
        # Look at first few test rows after page break
        end_idx = min(len(line_contexts), page_break_idx + 5)
        for i in range(page_break_idx, end_idx):
            if line_contexts[i].role == 'TEST_ROW':
                text = line_contexts[i].text
                if re.search(r'\b(mg|g|L|mL|%|mmol|units)\b', text):
                    patterns['has_units'] += 1
                if re.search(r'\d+\s*-\s*\d+', text):
                    patterns['has_ranges'] += 1
                if re.search(r'\b\d+\.?\d*\b', text):
                    patterns['numeric_results'] += 1
        
        return patterns
    
    def _calculate_pattern_similarity(self, patterns1: Dict[str, int], patterns2: Dict[str, int]) -> float:
        """Calculate similarity between pattern dictionaries"""
        if not patterns1 and not patterns2:
            return 1.0
        
        total_diff = 0
        total_max = 0
        
        for key in patterns1.keys():
            val1 = patterns1[key]
            val2 = patterns2.get(key, 0)
            total_diff += abs(val1 - val2)
            total_max += max(val1, val2, 1)
        
        return 1.0 - (total_diff / total_max) if total_max > 0 else 0.0
    
    def _open_new_panel(self, context: LineContext):
        """Open a new panel"""
        # Close current panel if open
        if self.current_panel and self.current_panel.open:
            self.current_panel.close_panel()
        # Reset continuation flag when explicitly opening a new panel
        self._continue_panel_on_next_page = True
        
        # Extract panel name from text
        panel_name = self._clean_title(context.text)
        
        # Generate panel ID: name-page-idx format
        panel_idx = len(self.panels)
        panel_id = f"{panel_name.replace(' ', '-')}-{context.page}-{panel_idx}"
        
        # NEW: Extract panel codes and comments
        panel_codes = extract_codes_from_vicinity(context.__dict__, self._lines_data)
        panel_comments = extract_panel_comments(context.__dict__, self._lines_data)
        
        # Create new panel with enhanced fields
        self.current_panel = Panel(
            id=panel_id,
            name=panel_name,
            started_at_page=context.page,
            started_at_line=context.line_number,
            continuity_score=1.0,
            open=True,
            test_rows=[],
            # NEW: Enhanced panel fields
            panel_code=panel_codes.get('loinc') or panel_codes.get('cpt'),
            comments=panel_comments
        )

        self.panels.append(self.current_panel)

        # Attach header score and review reason if weak
        try:
            hdr_score = score_panel_header({
                'text': context.text,
                'is_bold': context.is_bold,
                'y_norm': context.y_norm,
            })
            setattr(self.current_panel, 'header_score', hdr_score)
            if hdr_score < self.header_strong_threshold:
                if not hasattr(self.current_panel, 'review_reasons') or self.current_panel.review_reasons is None:
                    self.current_panel.review_reasons = []
                self.current_panel.review_reasons.append('weak_panel_header')
        except Exception:
            pass

        # Track panel header for debugging
        self.panels_seen.append({
            "page": context.page,
            "id": panel_id,
            "name": panel_name
        })
    
    def _clean_title(self, text: str) -> str:
        """Clean panel title by removing prefixes and normalizing"""
        # Remove common prefixes/suffixes
        name = text.strip()
        # Remove "Ordered Items: " prefix as specified
        name = re.sub(r'^Ordered\s+Items:\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'^(SECTION_PANEL|Panel:|Section:)\s*', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*(Panel|Section)\s*$', '', name, flags=re.IGNORECASE)
        
        # Clean up whitespace
        name = ' '.join(name.split())
        
        return name or "Unnamed Panel"
    
    def _normalize_title(self, text: str) -> str:
        """Normalize title text for panel naming"""
        return self._clean_title(text)
    
    def _open_new_panel_fallback(self, context: LineContext):
        """Open a new panel using fallback rule for panel detection"""
        # Close current panel if open
        if self.current_panel and self.current_panel.open:
            self.current_panel.close_panel()
        # Reset continuation flag when explicitly opening a new panel
        self._continue_panel_on_next_page = True
        
        # Extract panel name from text
        panel_name = self._normalize_title(context.text)
        
        # Generate panel ID: name-page-idx format with fallback indicator
        panel_idx = len(self.panels)
        panel_id = f"{panel_name.replace(' ', '-')}-{context.page}-{panel_idx}-fallback"
        
        # Create new panel
        self.current_panel = Panel(
            id=panel_id,
            name=panel_name,
            started_at_page=context.page,
            started_at_line=context.line_number,
            continuity_score=0.8,  # Slightly lower than normal but still good
            open=True,
            test_rows=[]
        )
        
        # Add source metadata
        self.current_panel.source = 'fallback_rule'
        
        self.panels.append(self.current_panel)
        
        # Track panel header for debugging
        self.panels_seen.append({
            "page": context.page,
            "id": panel_id,
            "name": panel_name,
            "source": "fallback_rule"
        })
        
        logger.info(f"🔄 Opened panel via fallback rule: '{panel_name}' (role was {context.role})")
    
    def _attach_test_row(self, context: LineContext):
        """Attach test row to current panel"""
        if not self.current_panel or not self.current_panel.open:
            # This should not happen in the new logic, but keep as safety
            self._create_default_panel(context)
        
        # Parse test row
        test_row = self._parse_test_row(context)
        
        # Attach to current panel
        self.current_panel.add_test_row(test_row)
    
    def _create_default_panel(self, context: LineContext):
        """Create a default panel when none exists"""
        panel_idx = len(self.panels)
        panel_id = f"Default-Panel-{context.page}-{panel_idx}"
        # NEW: Try to extract any codes/comments even for default panel
        panel_codes = extract_codes_from_vicinity(context.__dict__, self._lines_data)
        panel_comments = extract_panel_comments(context.__dict__, self._lines_data)
        
        self.current_panel = Panel(
            id=panel_id,
            name=f"Panel {panel_idx + 1}",
            started_at_page=context.page,
            started_at_line=context.line_number,
            continuity_score=0.5,
            open=True,
            test_rows=[],
            # NEW: Enhanced panel fields
            panel_code=panel_codes.get('loinc') or panel_codes.get('cpt'),
            comments=panel_comments
        )
        
        self.panels.append(self.current_panel)
        
        # Track for debugging
        self.panels_seen.append({
            "page": context.page,
            "id": panel_id,
            "name": f"Panel {panel_idx + 1}"
        })
        # Allow attaching rows now
        self._continue_panel_on_next_page = True
    
    def _parse_test_row(self, context: LineContext) -> TestRow:
        """Parse a test row to extract structured data"""
        text = context.text.strip()
        
        # Initialize test row
        test_row = TestRow(
            text=text,
            page=context.page,
            line_number=context.line_number,
            y_norm=context.y_norm
        )
        
        # Try different parsing patterns
        self._parse_numeric_result(test_row)
        if not test_row.result_value:
            self._parse_text_result(test_row)
        
        # Extract additional components
        self._extract_reference_range(test_row)
        self._extract_flag(test_row)
        
        # Check if parsing produced incomplete results and try stitching
        parsing_completeness = self._calculate_parsing_completeness(test_row)
        if parsing_completeness < 0.5:  # Incomplete parsing
            stitched_result = self._try_stitching_nearby_lines(context)
            if stitched_result and stitched_result['confidence'] > parsing_completeness:
                # Apply stitched results
                self._apply_stitched_result(test_row, stitched_result)
                test_row.stitched = True
                test_row.stitch_confidence = stitched_result['confidence']
                logger.debug(f"Applied stitching to test row at line {context.line_number}: {stitched_result['confidence']:.2f} confidence")
        
        # NEW: Apply enhanced extraction for codes, methodology, comments, etc.
        test_row = enhance_test_row_with_bio_tags(test_row, context.__dict__, self._lines_data)
        
        return test_row
    
    def _parse_numeric_result(self, test_row: TestRow):
        """Parse numeric test result"""
        match = self.test_patterns['numeric_result'].match(test_row.text)
        if match:
            test_row.test_name = match.group(1).strip()
            test_row.result_value = match.group(2).strip()
            test_row.units = match.group(3).strip() if match.group(3) else None
            remaining = match.group(4).strip() if match.group(4) else ""
            
            # Extract reference range from remaining text
            if remaining and not test_row.reference_range:
                test_row.reference_range = remaining
    
    def _parse_text_result(self, test_row: TestRow):
        """Parse text-based test result"""
        match = self.test_patterns['text_result'].match(test_row.text)
        if match:
            test_row.test_name = match.group(1).strip()
            test_row.result_value = match.group(2).strip()
            remaining = match.group(3).strip() if match.group(3) else ""
            
            if remaining:
                test_row.reference_range = remaining
    
    def _extract_reference_range(self, test_row: TestRow):
        """Extract reference range from text"""
        if test_row.reference_range:
            return  # Already extracted
        
        # Look for range patterns in the full text
        range_match = self.test_patterns['range_pattern'].search(test_row.text)
        if range_match:
            test_row.reference_range = range_match.group(0)
    
    def _extract_flag(self, test_row: TestRow):
        """Extract abnormal flags from text"""
        flag_match = self.test_patterns['flag_pattern'].search(test_row.text)
        if flag_match:
            test_row.flag = flag_match.group(0).upper()
    
    def _calculate_parsing_completeness(self, test_row: TestRow) -> float:
        """Calculate how complete the test row parsing is"""
        completeness = 0.0
        
        # Basic structure (test name or result value) = 0.3
        if test_row.test_name or test_row.result_value:
            completeness += 0.3
        
        # Result value = 0.3
        if test_row.result_value:
            completeness += 0.3
        
        # Units = 0.2
        if test_row.units:
            completeness += 0.2
        
        # Reference range = 0.1
        if test_row.reference_range:
            completeness += 0.1
        
        # Flag = 0.1
        if test_row.flag:
            completeness += 0.1
        
        return min(completeness, 1.0)
    
    def _try_stitching_nearby_lines(self, context: LineContext) -> Optional[Dict]:
        """Try to stitch nearby lines for a better test row"""
        if not hasattr(self, '_current_line_contexts'):
            return None
        
        # Find nearby lines on the same page with similar y coordinates
        nearby_lines = []
        current_y = context.y_norm
        
        # Look at lines within a window around current line
        current_idx = context.line_number
        search_window = 5  # Look at ±5 lines
        
        start_idx = max(0, current_idx - search_window)
        end_idx = min(len(self._current_line_contexts), current_idx + search_window + 1)
        
        for i in range(start_idx, end_idx):
            line_ctx = self._current_line_contexts[i]
            # Only consider lines on same page
            if line_ctx.page != context.page:
                continue
            
            # Include lines with similar y coordinates or TEST_ROW role
            if (abs(line_ctx.y_norm - current_y) <= 0.006 or 
                line_ctx.role == 'TEST_ROW'):
                nearby_lines.append({
                    'text': line_ctx.text,
                    'y_norm': line_ctx.y_norm,
                    'x_left': line_ctx.x_left,
                    'x_right': line_ctx.x_right,
                    'line_number': line_ctx.line_number,
                    'role': line_ctx.role
                })
        
        if len(nearby_lines) >= 2:
            return stitch_testrow_candidates(nearby_lines)
        
        return None
    
    def _apply_stitched_result(self, test_row: TestRow, stitched_result: Dict):
        """Apply stitched result to test row"""
        if stitched_result.get('test_name'):
            test_row.test_name = stitched_result['test_name']
        
        if stitched_result.get('result_value'):
            test_row.result_value = stitched_result['result_value']
        
        if stitched_result.get('units'):
            test_row.units = stitched_result['units']
        
        if stitched_result.get('reference_range'):
            test_row.reference_range = stitched_result['reference_range']
        
        if stitched_result.get('flag'):
            test_row.flag = stitched_result['flag']
        
        # Update text to reflect stitched content
        if 'source_lines' in stitched_result:
            texts = [line.get('text', '') for line in stitched_result['source_lines']]
            test_row.text = ' '.join(filter(None, texts))
    
    def _second_pass(self, processed_lines: List[LineContext]):
        """Second pass: targeted repairs across page breaks"""
        page_breaks = self._identify_page_breaks(processed_lines)
        
        # 1) Repair sandwiched TEST_ROW blocks between identical headers
        for page_break in page_breaks:
            repair = self._detect_sandwiched_block(processed_lines, page_break)
            if repair:
                self._apply_repair(repair)
                self.repairs_made += 1
        
        # 2) Minimal greedy repair as fallback
        for page_break in page_breaks:
            repairs = self._evaluate_repair_options(processed_lines, page_break)
            if repairs:
                best_repair = min(repairs, key=lambda r: r['cost'])
                # Only apply if we support the repair type
                if best_repair.get('type') == 'sandwich_move' and best_repair['cost'] < float('inf'):
                    self._apply_repair(best_repair)
                    self.repairs_made += 1

    def _detect_sandwiched_block(self, processed_lines: List[LineContext], page_break_idx: int) -> Optional[Dict]:
        """Detect a TEST_ROW block sandwiched between the same headers on neighboring pages."""
        # Find the header before the break
        pre_hdr_idx = None
        for i in range(page_break_idx - 1, -1, -1):
            if processed_lines[i].role == 'SECTION_PANEL':
                pre_hdr_idx = i
                break
        if pre_hdr_idx is None:
            return None
        pre_hdr_name = self._clean_title(processed_lines[pre_hdr_idx].text)
        pre_hdr_page = processed_lines[pre_hdr_idx].page
        
        # Find the header after the break within first P non-header lines
        seen = 0
        post_hdr_idx = None
        for i in range(page_break_idx, min(len(processed_lines), page_break_idx + 50)):
            lc = processed_lines[i]
            if lc.role in ['PAGE_HEADER', 'PAGE_FOOTER']:
                continue
            seen += 1
            if lc.role == 'SECTION_PANEL':
                post_hdr_idx = i
                break
            if seen >= self.page_break_lookahead:
                break
        if post_hdr_idx is None:
            return None
        post_hdr_name = self._clean_title(processed_lines[post_hdr_idx].text)
        post_hdr_page = processed_lines[post_hdr_idx].page
        if pre_hdr_name != post_hdr_name or (post_hdr_page - pre_hdr_page) != 1:
            return None
        
        # Collect TEST_ROW contexts between break and the post header
        between_contexts = [lc for lc in processed_lines[page_break_idx:post_hdr_idx] if lc.role == 'TEST_ROW']
        if not between_contexts:
            return None
        line_nums = set(lc.line_number for lc in between_contexts)
        
        # Identify panels for pre and post headers
        pre_panel_idx = None
        for idx, p in enumerate(self.panels):
            if p.started_at_line == pre_hdr_idx and self._clean_title(p.name) == pre_hdr_name:
                pre_panel_idx = idx
        if pre_panel_idx is None:
            for idx, p in reversed(list(enumerate(self.panels))):
                if p.started_at_page == pre_hdr_page and self._clean_title(p.name) == pre_hdr_name:
                    pre_panel_idx = idx
                    break
        if pre_panel_idx is None:
            return None
        post_panel_idx = None
        for idx, p in enumerate(self.panels):
            if p.started_at_line == post_hdr_idx:
                post_panel_idx = idx
                break
        if post_panel_idx is None:
            for idx, p in enumerate(self.panels):
                if p.started_at_page == post_hdr_page and self._clean_title(p.name) == post_hdr_name:
                    post_panel_idx = idx
                    break
        if post_panel_idx is None:
            return None
        
        post_panel = self.panels[post_panel_idx]
        move_rows = [tr for tr in post_panel.test_rows if tr.line_number in line_nums]
        if not move_rows:
            return None
        return {
            'type': 'sandwich_move',
            'pre_panel_idx': pre_panel_idx,
            'post_panel_idx': post_panel_idx,
            'move_rows': move_rows,
        }
    
    def _identify_page_breaks(self, processed_lines: List[LineContext]) -> List[int]:
        """Identify line indices where page breaks occur"""
        page_breaks = []
        current_page = 1
        
        for i, context in enumerate(processed_lines):
            if context.page > current_page:
                page_breaks.append(i)
                current_page = context.page
        
        return page_breaks
    
    def _evaluate_repair_options(self, processed_lines: List[LineContext], page_break_idx: int) -> List[Dict]:
        """Evaluate repair options for a page break"""
        repairs = []
        
        # Find test rows around the page break
        pre_break_tests = []
        post_break_tests = []
        
        # Look backward for test rows
        for i in range(page_break_idx - 1, max(0, page_break_idx - 10), -1):
            if processed_lines[i].role == 'TEST_ROW':
                pre_break_tests.append(i)
            elif processed_lines[i].role == 'SECTION_PANEL':
                break
        
        # Look forward for test rows  
        for i in range(page_break_idx, min(len(processed_lines), page_break_idx + 10)):
            if processed_lines[i].role == 'TEST_ROW':
                post_break_tests.append(i)
            elif processed_lines[i].role == 'SECTION_PANEL':
                break
        
        if not post_break_tests:
            return repairs
        
        # Option 1: Continue current panel
        if pre_break_tests:
            cost = self._calculate_repair_cost(processed_lines, pre_break_tests[-1], post_break_tests[0], 'continue')
            repairs.append({
                'type': 'continue',
                'cost': cost,
                'pre_test_idx': pre_break_tests[-1],
                'post_test_idx': post_break_tests[0]
            })
        
        # Option 2: Start new panel
        cost = self._calculate_repair_cost(processed_lines, None, post_break_tests[0], 'new_panel')
        repairs.append({
            'type': 'new_panel',
            'cost': cost,
            'post_test_idx': post_break_tests[0]
        })
        
        return repairs
    
    def _calculate_repair_cost(self, processed_lines: List[LineContext], 
                              pre_test_idx: Optional[int], post_test_idx: int, 
                              repair_type: str) -> float:
        """Calculate cost for a repair option"""
        cost = 0.0
        
        if repair_type == 'continue' and pre_test_idx is not None:
            # Cost for continuing: penalty for panel switches, bonus for coherence
            pre_text = processed_lines[pre_test_idx].text
            post_text = processed_lines[post_test_idx].text
            
            coherence_score = self._calculate_text_coherence(pre_text, post_text)
            cost = self.cost_weight_switches * 0.5 - self.cost_weight_coherence * coherence_score
            
        elif repair_type == 'new_panel':
            # Cost for new panel: penalty for creating new panel
            cost = self.cost_weight_switches * 1.0
        
        return max(0.0, cost)
    
    def _calculate_text_coherence(self, text1: str, text2: str) -> float:
        """Calculate coherence between two test row texts"""
        # Simple heuristic: check for similar patterns
        patterns1 = self._extract_text_patterns(text1)
        patterns2 = self._extract_text_patterns(text2)
        
        return self._calculate_pattern_similarity(patterns1, patterns2)
    
    def _repair_split_rows(self, panels: List[Panel]):
        """
        Second-pass repair for split rows where value, unit, or ref_range 
        appear on subsequent lines within the same panel.
        """
        if not panels:
            return
            
        total_repairs = 0
        
        for panel in panels:
            panel_repairs = 0
            test_rows = panel.test_rows.copy()  # Work on a copy
            consumed_rows = set()  # Track rows to remove
            
            for i, test_row in enumerate(test_rows):
                if i in consumed_rows:
                    continue
                    
                # Check if this test row needs repair (has value but missing unit/ref_range)
                needs_repair = (test_row.result_value and 
                               (not test_row.units or not test_row.reference_range))
                
                if not needs_repair:
                    continue
                
                # Apply guardrails before repair
                if self._should_demote_to_comment(test_row):
                    # Don't repair, will be filtered out later
                    continue
                
                # Look ahead up to next 2 physical lines in the same panel
                repair_made = False
                for j in range(i + 1, min(i + 3, len(test_rows))):
                    if j in consumed_rows:
                        continue
                        
                    neighbor_row = test_rows[j]
                    
                    # Check proximity conditions
                    if not self._rows_are_nearby(test_row, neighbor_row):
                        break  # Too far, stop looking
                    
                    # Check if neighbor has useful fields to merge
                    merge_result = self._try_merge_fields(test_row, neighbor_row)
                    if merge_result:
                        # Apply the merge
                        if merge_result.get('unit'):
                            test_row.units = merge_result['unit']
                            try:
                                test_row.unit_repaired = True
                            except Exception:
                                pass
                        if merge_result.get('ref_range'):
                            test_row.reference_range = merge_result['ref_range']
                            try:
                                test_row.ref_repaired = True
                            except Exception:
                                pass
                        
                        # Mark neighbor for consumption if it has no remaining fields
                        if self._has_no_remaining_fields(neighbor_row, merge_result):
                            consumed_rows.add(j)
                        
                        # Mark as repaired
                        test_row.repaired_split = True
                        panel_repairs += 1
                        repair_made = True
                        break  # Found what we need
            
            # Remove consumed rows from the panel
            if consumed_rows:
                panel.test_rows = [row for idx, row in enumerate(test_rows) if idx not in consumed_rows]
            
            # Add warning if >25% rows were repaired
            if panel_repairs > 0:
                repair_percentage = panel_repairs / max(len(panel.test_rows), 1)
                if repair_percentage > 0.25:
                    if not hasattr(panel, 'review_reasons'):
                        panel.review_reasons = []
                    panel.review_reasons.append(f"High split-row repair rate: {panel_repairs}/{len(panel.test_rows)} rows repaired")

            # Column-based repair on same page if units/reference_range still missing
            for tr in panel.test_rows:
                try:
                    if (tr.result_value and (not tr.units or not tr.reference_range)):
                        if self._repair_from_page_columns(tr):
                            tr.repaired_split = True
                except Exception:
                    continue

    def _text_is_unit(self, text: str) -> bool:
        if not text:
            return False
        # Reuse a small whitelist
        UNIT_WHITELIST = {
            'mg/dL', 'g/dL', 'mEq/L', 'mmol/L', 'uIU/mL', 'IU/L', 'ng/mL', 'pg/mL',
            'mcg/dL', 'ug/dL', 'mg/L', 'g/L', '%', 'U/L', 'mU/L', 'K/uL', 'M/uL'
        }
        return text.strip() in UNIT_WHITELIST

    def _derive_page_anchors(self, page: int):
        # Derive/cached anchors for a page
        if page in self._page_unit_anchor and page in self._page_ref_anchor:
            return
        page_ctxs = [ctx for ctx in getattr(self, '_current_line_contexts', []) if ctx.page == page]
        unit_xs = [ctx.x_left for ctx in page_ctxs if self._text_is_unit(ctx.text)]
        ref_xs = [ctx.x_left for ctx in page_ctxs if self._simple_ref_range_line_re.match((ctx.text or '').strip())]
        self._page_unit_anchor[page] = float(median(unit_xs)) if unit_xs else None
        self._page_ref_anchor[page] = float(median(ref_xs)) if ref_xs else None

    def _repair_from_page_columns(self, test_row: TestRow) -> bool:
        """Attach units/ref_range from same-page lines using column anchors.
        Returns True if any repair applied.
        """
        page = getattr(test_row, 'page', None) or 1
        y0 = getattr(test_row, 'y_norm', None)
        if y0 is None:
            return False
        self._derive_page_anchors(page)
        unit_anchor = self._page_unit_anchor.get(page)
        ref_anchor = self._page_ref_anchor.get(page)
        # Fallback windows if anchors missing
        unit_low, unit_high = (350.0, 420.0)
        ref_low, ref_high = (430.0, 520.0)
        # If anchors exist, narrow window around them
        if unit_anchor is not None:
            unit_low, unit_high = (unit_anchor - 40.0, unit_anchor + 40.0)
        if ref_anchor is not None:
            ref_low, ref_high = (ref_anchor - 45.0, ref_anchor + 45.0)

        candidates = [ctx for ctx in getattr(self, '_current_line_contexts', [])
                      if ctx.page == page and abs((ctx.y_norm or 0.0) - y0) <= 0.003]
        repaired = False
        # Units repair
        if not getattr(test_row, 'units', None):
            best = None
            best_key = float('inf')
            center = unit_anchor if unit_anchor is not None else (unit_low + unit_high) / 2.0
            for ctx in candidates:
                x = float(ctx.x_left or 0.0)
                if x < unit_low or x > unit_high:
                    continue
                if not self._text_is_unit(ctx.text):
                    continue
                key = abs(x - center)
                if key < best_key:
                    best_key = key
                    best = ctx
            if best is not None:
                test_row.units = (best.text or '').strip()
                try:
                    test_row.unit_repaired = True
                except Exception:
                    pass
                repaired = True
        # Reference range repair
        if not getattr(test_row, 'reference_range', None):
            best = None
            best_key = float('inf')
            center = ref_anchor if ref_anchor is not None else (ref_low + ref_high) / 2.0
            for ctx in candidates:
                x = float(ctx.x_left or 0.0)
                if x < ref_low or x > ref_high:
                    continue
                if not self._simple_ref_range_line_re.match((ctx.text or '').strip()):
                    continue
                key = abs(x - center)
                if key < best_key:
                    best_key = key
                    best = ctx
            if best is not None:
                test_row.reference_range = (best.text or '').strip()
                try:
                    test_row.ref_repaired = True
                except Exception:
                    pass
                repaired = True
        return repaired
    
    def _should_demote_to_comment(self, test_row: TestRow) -> bool:
        """
        Apply guardrails to determine if a test_row should be demoted to COMMENT.
        Returns True if the row should be demoted.
        """
        test_name = test_row.test_name or ""
        result_value = test_row.result_value or ""
        units = test_row.units or ""
        
        # Guardrail 1: Test name ends with ":" and contains problematic terms
        if test_name.endswith(":"):
            problematic_terms = {"Specimen ID", "Acct #", "Phone", "Client", "Rte"}
            if any(term in test_name for term in problematic_terms):
                return True
        
        # Guardrail 2: No numeric value and no unit from whitelist  
        has_numeric_value = bool(re.search(r'\d', result_value))
        
        # Unit whitelist (subset for guardrails)
        unit_whitelist = {
            'mg/dL', 'g/dL', 'mEq/L', 'mmol/L', 'uIU/mL', 'IU/L', 'ng/mL', 'pg/mL',
            'mcg/dL', 'ug/dL', 'mg/L', 'g/L', '%', 'ratio', 'index', 'units/L',
            'U/L', 'mU/L', 'fL', 'pg', 'K/uL', 'M/uL', 'cells/uL', 'per hpf',
            'copies/mL', 'cells/mL', 'mg', 'g', 'mL', 'L', 'cm', 'mm', 'bpm'
        }
        
        has_valid_unit = units in unit_whitelist
        
        if not has_numeric_value and not has_valid_unit:
            return True
        
        return False
    
    def _rows_are_nearby(self, row1: TestRow, row2: TestRow) -> bool:
        """
        Check if two rows are nearby enough to consider for merging.
        Uses y_norm difference < 0.06 OR column overlap if x coords available.
        """
        # Must be on same page
        if row1.page != row2.page:
            return False
        
        # Check y-coordinate proximity (within 0.06 normalized units)
        y_diff = abs(row1.y_norm - row2.y_norm)
        if y_diff < 0.06:
            return True
        
        # Check column overlap if x coordinates are available
        if (hasattr(row1, 'x_left') and hasattr(row1, 'x_right') and
            hasattr(row2, 'x_left') and hasattr(row2, 'x_right')):
            
            # Check for any overlap in x ranges
            overlap = (row1.x_left < row2.x_right and row2.x_left < row1.x_right)
            return overlap
        
        return False
    
    def _try_merge_fields(self, target_row: TestRow, source_row: TestRow) -> Optional[Dict[str, str]]:
        """
        Try to merge unit or ref_range fields from source_row into target_row.
        Returns dict with fields that can be merged, or None if no merge possible.
        """
        merge_result = {}
        
        # Unit whitelist for recognition
        unit_whitelist = {
            'mg/dL', 'g/dL', 'mEq/L', 'mmol/L', 'uIU/mL', 'IU/L', 'ng/mL', 'pg/mL',
            'mcg/dL', 'ug/dL', 'mg/L', 'g/L', '%', 'ratio', 'index', 'units/L',
            'U/L', 'mU/L', 'fL', 'pg', 'K/uL', 'M/uL', 'cells/uL', 'per hpf',
            'copies/mL', 'cells/mL', 'mg', 'g', 'mL', 'L', 'cm', 'mm', 'bpm'
        }
        
        source_text = source_row.text or ""
        
        # Try to extract unit if target is missing one
        if not target_row.units:
            # Check if source row has a unit from whitelist
            words = source_text.split()
            for word in words:
                if word.strip() in unit_whitelist:
                    merge_result['unit'] = word.strip()
                    break
        
        # Try to extract reference range if target is missing one
        if not target_row.reference_range:
            # Look for reference range patterns
            ref_patterns = [
                r"\b\d+(\.\d+)?\s*[-–]\s*\d+(\.\d+)?\b",  # "70-100" or "2.5–4.0"
                r"[≤≥<>]\s*\d+(\.\d+)?",  # "≤4.0" or ">100"
                r"\b(NORMAL|ABNORMAL|HIGH|LOW|POSITIVE|NEGATIVE)\b"  # Qualitative ranges
            ]
            
            for pattern in ref_patterns:
                match = re.search(pattern, source_text, re.IGNORECASE)
                if match:
                    merge_result['ref_range'] = match.group(0)
                    break
        
        return merge_result if merge_result else None
    
    def _has_no_remaining_fields(self, row: TestRow, merged_fields: Dict[str, str]) -> bool:
        """
        Check if a row has no remaining useful fields after merging,
        so it can be safely consumed (removed).
        """
        # If the entire text of the row was consumed in merging, it can be removed
        row_text = (row.text or "").strip()
        
        # Check if row text consists only of the merged fields
        merged_unit = merged_fields.get('unit', '')
        merged_ref = merged_fields.get('ref_range', '')
        
        # Simple heuristic: if row text is very short and contains only merged content
        remaining_text = row_text
        if merged_unit:
            remaining_text = remaining_text.replace(merged_unit, '').strip()
        if merged_ref:
            remaining_text = remaining_text.replace(merged_ref, '').strip()
        
        # If very little text remains (just whitespace, punctuation), consume the row
        remaining_meaningful = re.sub(r'[^\w]', '', remaining_text)
        return len(remaining_meaningful) <= 2
    
    def _extract_text_patterns(self, text: str) -> Dict[str, int]:
        """Extract patterns from a single text line"""
        patterns = {
            'has_units': 1 if re.search(r'\b(mg|g|L|mL|%|mmol|units)\b', text) else 0,
            'has_ranges': 1 if re.search(r'\d+\s*-\s*\d+', text) else 0,
            'numeric_results': 1 if re.search(r'\b\d+\.?\d*\b', text) else 0
        }
        return patterns
    
    def _apply_repair(self, repair: Dict):
        """Apply a repair to the panel structure"""
        if repair.get('type') == 'sandwich_move':
            pre_panel_idx: int = repair['pre_panel_idx']
            post_panel_idx: int = repair['post_panel_idx']
            move_rows: List[TestRow] = repair['move_rows']
            post_panel = self.panels[post_panel_idx]
            pre_panel = self.panels[pre_panel_idx]
            # Remove rows from post panel by identity
            post_panel.test_rows = [tr for tr in post_panel.test_rows if tr not in move_rows]
            for tr in move_rows:
                pre_panel.add_test_row(tr)
            return
        # Other repair types can be added here when needed
    
    def _third_pass_continuity_repair(self, processed_lines: List[LineContext]):
        """Third pass: repair synthetic panels when proper headers appear later"""
        if not self.paneling_metadata['opened_synthetic']:
            return  # No synthetic panels to repair
        
        # Find synthetic panels that could be repaired
        synthetic_panels = [panel for panel in self.panels if hasattr(panel, 'origin') and panel.origin == 'synthetic']
        
        for synthetic_panel in synthetic_panels:
            repair_candidate = self._find_repair_candidate(synthetic_panel, processed_lines)
            if repair_candidate:
                self._apply_continuity_repair(synthetic_panel, repair_candidate)
                self.paneling_metadata['repaired_at_page'] = repair_candidate.page
                logger.info(f"🔧 Repaired synthetic panel '{synthetic_panel.id}' with proper header '{repair_candidate.text}' at page {repair_candidate.page}")
    
    def _find_repair_candidate(self, synthetic_panel: Panel, processed_lines: List[LineContext]) -> Optional[LineContext]:
        """Find a SECTION_PANEL header that could repair a synthetic panel"""
        synthetic_start_line = synthetic_panel.started_at_line
        
        # Look for SECTION_PANEL within 10 lines after the synthetic panel start
        search_end = min(len(processed_lines), synthetic_start_line + 10)
        
        for i in range(synthetic_start_line, search_end):
            if i < len(processed_lines):
                context = processed_lines[i]
                if (context.role == 'SECTION_PANEL' and 
                    context.page == synthetic_panel.started_at_page):
                    return context
        
        return None
    
    def _apply_continuity_repair(self, synthetic_panel: Panel, repair_header: LineContext):
        """Apply continuity repair by reassigning test rows to proper panel"""
        # Create new proper panel
        panel_idx = len(self.panels)
        panel_id = f"repaired-panel-{repair_header.page}-{panel_idx}"
        
        new_panel = Panel(
            id=panel_id,
            name=self._clean_title(repair_header.text),
            started_at_page=repair_header.page,
            started_at_line=repair_header.line_number,
            continuity_score=0.8,  # Higher confidence after repair
            open=False,  # Closed panel
            test_rows=[]
        )
        
        # Move test rows from synthetic panel to new panel
        for test_row in synthetic_panel.test_rows:
            new_panel.add_test_row(test_row)
        
        # Replace synthetic panel with repaired panel
        synthetic_index = self.panels.index(synthetic_panel)
        self.panels[synthetic_index] = new_panel
        
        # Update panels_seen for debugging
        self.panels_seen.append({
            "page": repair_header.page,
            "id": panel_id,
            "name": new_panel.name,
            "source": "continuity_repair",
            "repaired_from": synthetic_panel.id
        })
    
    def _second_pass_repairs(self, panels) -> int:
        """
        Walk each panel and apply small repairs; return total repairs.
        Kept separate to avoid indentation regressions.
        """
        total_repairs = 0
        for panel in panels:
            panel_repairs = sum(
                1 for tr in getattr(panel, "test_rows", [])
                if bool(getattr(tr, "repaired_split", False))
            )
            total_repairs += panel_repairs
        return total_repairs

    def _apply_scoring(self, result, classifier_probabilities=None) -> None:
        """
        Compute panel + document scores and attach to `result`.
        `classifier_probabilities` may be:
          - dict: {line_number: {label: proba, ...}}
          - list aligned by line_number with dicts/None
          - list of objects: {"line_number": n, "distribution": {...}}
        """
        # Ask the scorer for document & per-panel scores
        document_score, panel_scores = self.scorer.score_document(
            result.panels,
            classifier_probabilities
        )

        # Normalize & attach document score
        try:
            result.document_score = float(document_score) if document_score is not None else 0.0
        except Exception:
            result.document_score = 0.0

        # Attach per-panel scores, length-safe
        if not isinstance(panel_scores, (list, tuple)):
            panel_scores = []
        for i, panel in enumerate(getattr(result, "panels", []) or []):
            try:
                score_val = float(panel_scores[i]) if i < len(panel_scores) else 0.0
            except Exception:
                score_val = 0.0
            setattr(panel, "score", score_val)

        # Apply repairs and get count
        repairs_made = self._second_pass_repairs(result.panels)
        result.total_repairs = int(repairs_made)
    
    def _process_buffered_test_rows(self, test_row_buffer: List[LineContext]):
        """Process buffered test rows by attaching them to current panel"""
        if not test_row_buffer:
            return
        
        for context in test_row_buffer:
            if self.current_panel and self.current_panel.open:
                self._attach_test_row(context)
    
    def _create_fallback_panel(self, test_row_buffer: List[LineContext]):
        """Create fallback panel for orphaned test rows"""
        if not test_row_buffer:
            return
        
        # Use the first test row's location for panel creation
        first_context = test_row_buffer[0]
        panel_idx = len(self.panels)
        # ID like "panel_<n>" (1-based index)
        panel_id = f"panel_{panel_idx+1}"
        
        # Try to guess a better panel name from previous lines
        guessed_name = self._guess_panel_name(first_context)
        continuity_score = 0.3  # Default for auto-created panels
        
        # Boost continuity score slightly if we found a likely header
        if guessed_name != "UNNAMED":
            continuity_score = 0.4
        
        self.current_panel = Panel(
            id=panel_id,
            name=guessed_name,
            started_at_page=first_context.page,
            started_at_line=first_context.line_number,
            continuity_score=continuity_score,
            open=True,
            test_rows=[]
        )
        
        self.panels.append(self.current_panel)
        
        # Track for debugging
        self.panels_seen.append({
            "page": first_context.page,
            "id": panel_id,
            "name": guessed_name
        })
        
        # Attach all buffered test rows
        for context in test_row_buffer:
            self._attach_test_row(context)
        
        # Boost continuity score if subsequent test rows share common units
        self._boost_continuity_for_common_units(self.current_panel)

    def _guess_panel_name(self, context: LineContext) -> str:
        """
        Guess a panel name by looking back up to 8 non-junk, non-header lines for a likely header.
        
        Args:
            context: The LineContext where the panel is being created
            
        Returns:
            Guessed panel name, or "UNNAMED" if no suitable header found
        """
        if not hasattr(self, '_current_line_contexts'):
            return "UNNAMED"
        
        # Look back up to 8 non-junk, non-header lines
        current_idx = context.line_number
        lines_checked = 0
        max_lines_to_check = 8
        
        # Start from the line before current context
        for i in range(current_idx - 1, -1, -1):
            if i >= len(self._current_line_contexts):
                continue
                
            line_ctx = self._current_line_contexts[i]
            
            # Skip different pages
            if line_ctx.page != context.page:
                break
                
            # Skip quarantine, junk, and header/footer lines
            if (line_ctx.in_quarantine or 
                line_ctx.role in ['JUNK', 'PAGE_HEADER', 'PAGE_FOOTER', 'TEST_ROW']):
                continue
                
            lines_checked += 1
            if lines_checked > max_lines_to_check:
                break
                
            text = (line_ctx.text or "").strip()
            if not text:
                continue
                
            # Check if this looks like a good header candidate
            if self._is_likely_panel_header(text, line_ctx):
                # Clean and return the guessed name
                return self._clean_title(text)
        
        return "UNNAMED"
    
    def _is_likely_panel_header(self, text: str, line_ctx: LineContext) -> bool:
        """
        Check if a text line is likely to be a panel header.
        
        Args:
            text: The text content of the line
            line_ctx: The LineContext for additional formatting info
            
        Returns:
            True if the line looks like a panel header
        """
        # Prefer lines with isBold or ALL CAPS words ≥ 2 tokens
        words = text.split()
        
        # Priority 1: Bold text with ≥ 2 tokens
        if line_ctx.is_bold and len(words) >= 2:
            return True
            
        # Priority 2: Text with ALL CAPS words ≥ 2 tokens
        caps_words = [w for w in words if w.isupper() and len(w) >= 2]
        if len(caps_words) >= 2:
            return True
            
        # Priority 3: Lines with ≥ 2 alphabetic tokens (fallback)
        alpha_words = [w for w in words if re.search(r'[a-zA-Z]{2,}', w)]
        if len(alpha_words) >= 2:
            return True
            
        return False

    def _boost_continuity_for_common_units(self, panel: Panel):
        """
        Boost panel continuity score slightly if test rows share common units.
        
        Args:
            panel: The Panel to analyze and potentially boost
        """
        if not panel or not panel.test_rows:
            return
            
        # Collect units from test rows
        units = []
        for test_row in panel.test_rows:
            if test_row.units:
                units.append(test_row.units.strip())
        
        if len(units) < 2:
            return  # Need at least 2 units to check commonality
            
        # Count unit frequency
        unit_counts = {}
        for unit in units:
            unit_counts[unit] = unit_counts.get(unit, 0) + 1
        
        # Check for common units (appears in >50% of rows with units)
        total_with_units = len(units)
        common_units = [unit for unit, count in unit_counts.items() 
                       if count / total_with_units > 0.5]
        
        if common_units:
            # Boost continuity score by 0.1 for unit commonality
            boost = 0.1
            old_score = panel.continuity_score
            panel.continuity_score = min(1.0, panel.continuity_score + boost)
            
            logger.debug(f"Boosted panel '{panel.name}' continuity from {old_score:.2f} to {panel.continuity_score:.2f} "
                        f"due to common units: {common_units}")

    def _should_open_fallback(self, line_contexts: List[LineContext], start_idx: int) -> bool:
        """Open an UNNAMED panel if K consecutive TEST_ROW within next M lines."""
        end_idx = min(len(line_contexts), start_idx + self._fallback_M)
        consecutive = 0
        for j in range(start_idx, end_idx):
            lc = line_contexts[j]
            if lc.in_quarantine:
                continue
            if lc.role == 'TEST_ROW':
                consecutive += 1
                if consecutive >= self._fallback_K:
                    return True
            else:
                consecutive = 0
        return False
    
    def _should_open_synthetic_panel(self, test_row_buffer: List[LineContext], current_context: LineContext) -> bool:
        """Check if we should open a synthetic panel for stitched TEST_ROWs in upper page area"""
        if len(test_row_buffer) < 2:  # Need at least 2 test rows
            return False
        
        # Check if we're in upper 35% of page (y_norm < 0.35)
        if current_context.y_norm > 0.35:
            return False
        
        # Count how many test rows in buffer are stitched (have good structure)
        stitched_count = 0
        for ctx in test_row_buffer:
            # Parse the test row to check if it would be stitched
            if hasattr(self, '_current_line_contexts'):
                # Check if this test row would benefit from stitching
                nearby_lines = self._get_nearby_lines_for_stitching(ctx)
                if len(nearby_lines) >= 2:
                    stitched_count += 1
        
        # Check if we have enough stitched test rows
        return stitched_count >= 2
    
    def _create_synthetic_panel(self, test_row_buffer: List[LineContext], current_context: LineContext):
        """Create a synthetic panel for early test rows"""
        if not test_row_buffer:
            return
        
        first_context = test_row_buffer[0]
        panel_idx = len(self.panels)
        panel_id = f"synthetic-panel-{current_context.page}-{panel_idx}"
        
        self.current_panel = Panel(
            id=panel_id,
            name="UNKNOWN PANEL",
            started_at_page=current_context.page,
            started_at_line=first_context.line_number,
            continuity_score=0.35,  # Lower confidence for synthetic panels
            open=True,
            test_rows=[]
        )
        
        # Mark as synthetic
        self.current_panel.origin = 'synthetic'
        
        self.panels.append(self.current_panel)
        self.paneling_metadata['opened_synthetic'] = True
        
        # Track for debugging
        self.panels_seen.append({
            "page": current_context.page,
            "id": panel_id,
            "name": "UNKNOWN PANEL",
            "source": "synthetic",
            "confidence": 0.35
        })
        
        # Attach all buffered test rows
        for context in test_row_buffer:
            self._attach_test_row(context)
        
        logger.info(f"🔧 Created synthetic panel '{panel_id}' with {len(test_row_buffer)} test rows in upper page area")
    
    def _get_nearby_lines_for_stitching(self, context: LineContext) -> List[Dict]:
        """Get nearby lines for stitching evaluation (helper for synthetic panel detection)"""
        if not hasattr(self, '_current_line_contexts'):
            return []
        
        nearby_lines = []
        current_y = context.y_norm
        current_idx = context.line_number
        
        search_window = 3  # Smaller window for synthetic panel detection
        start_idx = max(0, current_idx - search_window)
        end_idx = min(len(self._current_line_contexts), current_idx + search_window + 1)
        
        for i in range(start_idx, end_idx):
            line_ctx = self._current_line_contexts[i]
            if line_ctx.page != context.page:
                continue
            
            if (abs(line_ctx.y_norm - current_y) <= 0.006 or 
                line_ctx.role == 'TEST_ROW'):
                nearby_lines.append({
                    'text': line_ctx.text,
                    'y_norm': line_ctx.y_norm,
                    'x_left': line_ctx.x_left,
                    'x_right': line_ctx.x_right
                })
        
        return nearby_lines
    
    def _create_unknown_panels(self, test_row_contexts: List[LineContext]):
        """
        Create Unknown panels when no SECTION_PANEL headers found but TEST_ROW lines exist.
        Splits into multiple panels if there are long gaps between test row clusters.
        """
        if not test_row_contexts:
            return
        
        # Conservative gap threshold: more than 5 non-test lines starts a new panel
        gap_threshold = 5
        
        # Group test rows by clusters (split on large gaps)
        clusters = []
        current_cluster = []
        last_line_number = -1
        
        for ctx in test_row_contexts:
            # If there's a significant gap, start a new cluster
            if last_line_number != -1 and (ctx.line_number - last_line_number) > gap_threshold:
                if current_cluster:
                    clusters.append(current_cluster)
                    current_cluster = []
            
            current_cluster.append(ctx)
            last_line_number = ctx.line_number
        
        # Add the last cluster
        if current_cluster:
            clusters.append(current_cluster)
        
        # Create Unknown panels for each cluster
        for i, cluster in enumerate(clusters):
            if not cluster:
                continue
                
            first_ctx = cluster[0]
            panel_id = f"panel-{i+1}"
            panel_name = "Unknown"
            
            # Create Unknown panel
            unknown_panel = Panel(
                id=panel_id,
                name=panel_name,
                started_at_page=first_ctx.page,
                started_at_line=first_ctx.line_number,
                continuity_score=0.7,  # Moderate score for auto-created panels
                open=False,
                test_rows=[]
            )
            
            # Attach all test rows in this cluster
            for ctx in cluster:
                test_row = self._parse_test_row(ctx)
                unknown_panel.add_test_row(test_row)
            
            self.panels.append(unknown_panel)
            
            # Track for debugging
            self.panels_seen.append({
                "page": first_ctx.page,
                "id": panel_id,
                "name": panel_name,
                "source": "unknown_fallback",
                "test_row_count": len(cluster)
            })
            
            logger.info(f"🔄 Created Unknown panel '{panel_id}' with {len(cluster)} test rows (lines {cluster[0].line_number}-{cluster[-1].line_number})")
    
    def _validate_composition(self, result: ComposerResult):
        """Self-check validation for composition results"""
        import re
        
        # Check if document containing "CBC With Differential" or "Platelet" produces >= 1 panel
        panel_patterns = [
            r'CBC.*[Ww]ith.*[Dd]ifferential',
            r'Platelet',
            r'Comprehensive.*Metabolic.*Panel'
        ]
        
        found_expected_panel = False
        for panel_info in self.panels_seen:
            text = panel_info.get('name') or panel_info.get('text', '')
            for pattern in panel_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    found_expected_panel = True
                    logger.info(f"✅ Panel composition validation passed: Found panel '{text}'")
                    break
        
        if found_expected_panel and result.panels:
            logger.info(f"✅ Composition validation: {len(result.panels)} panels created")
        elif found_expected_panel and not result.panels:
            logger.warning(f"⚠️  Composition validation failed: Expected panels found in text but no panels created")
        
        # Log summary
        total_stitched = sum(1 for panel in result.panels 
                           for test_row in panel.test_rows 
                           if hasattr(test_row, 'stitched') and test_row.stitched)
        
        logger.info(f"Panel composition summary: {len(result.panels)} panels, {result.total_test_rows} test rows")
        if total_stitched > 0:
            logger.info(f"🔗 Stitched {total_stitched} test rows from fragmented lines")
        
        # Log any fallback panels created
        fallback_panels = [p for p in self.panels_seen if p.get('source') == 'fallback_rule']
        unknown_panels = [p for p in self.panels_seen if p.get('source') == 'unknown_fallback']
        
        if fallback_panels:
            logger.info(f"✅ Fallback panels created: {len(fallback_panels)} - {[p['name'] for p in fallback_panels]}")
        if unknown_panels:
            total_test_rows = sum(p.get('test_row_count', 0) for p in unknown_panels)
            logger.info(f"🔄 Unknown panels created: {len(unknown_panels)} panels with {total_test_rows} test rows total")
        if not fallback_panels and not unknown_panels:
            logger.debug("No fallback or unknown panels were needed")


if __name__ == "__main__":
    try:
        # Minimal smoke: one panel header and one test-row
        demo_lines = [
            {"page":1,"line_number":10,"text":"COMPREHENSIVE METABOLIC PANEL","role":"SECTION_PANEL","y_norm":0.15},
            {"page":1,"line_number":11,"text":"Glucose 101 mg/dL 70-99 H","role":"TEST_ROW","y_norm":0.18},
        ]
        pc = PanelComposer()
        res = pc.compose(demo_lines, classifier_probabilities=None)
        print("panels:", len(res.panels))
        if res.panels:
            print("tests_in_first_panel:", len(res.panels[0].test_rows))
    except ImportError as e:
        print(f"Smoke test skipped due to import issue (expected when running directly): {e}")
    except Exception as e:
        print(f"Smoke test failed: {e}")
