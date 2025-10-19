import re
from typing import List, Dict, Tuple

# Panel header patterns (case-insensitive)
PANEL_PATTERNS = re.compile(
    r'\b(CMP|COMPREHENSIVE METABOLIC|CBC|COMPLETE BLOOD COUNT|LIPID|TSH|THYROID|'
    r'BASIC METABOLIC PANEL|BMP)\b',
    re.IGNORECASE
)

# Test name lexicons for common panels
TEST_NAMES = {
    'CMP': ['sodium', 'potassium', 'chloride', 'co2', 'calcium', 'glucose', 'bun', 
           'creatinine', 'albumin', 'total protein', 'ast', 'alt', 'alk phos', 'bilirubin'],
    'CBC': ['wbc', 'rbc', 'hemoglobin', 'hgb', 'hematocrit', 'hct', 'mcv', 'mch', 
           'mchc', 'rdw', 'platelets', 'plt'],
    'LIPID': ['cholesterol', 'triglycerides', 'hdl', 'ldl', 'vldl', 'non-hdl'],
    'THYROID': ['tsh', 'free t4', 'free t3']
}

# Test row pattern (number + unit)
TEST_ROW_PATTERN = re.compile(
    r'\b\d+(\.\d+)?\s*(mg/dL|mmol/L|IU/L|U/L|g/dL|%|x10\^\d+|pg/mL|ng/mL|fL|pg)\b',
    re.IGNORECASE
)

# Units pattern
UNITS_PATTERN = re.compile(
    r'\b(mg/dL|mmol/L|g/dL|IU/L|U/L|pg/mL|ng/mL|x10\^\d+|%|fL|pg)\b',
    re.IGNORECASE
)

# Value pattern (allows comparison operators)
VALUE_PATTERN = re.compile(r'[<>=]*\s*\d+(\.\d+)?')

# Reference range pattern
REF_RANGE_PATTERN = re.compile(r'\(?\s*(\d+(\.\d+)?)\s*[-–]\s*(\d+(\.\d+)?)\s*\)?|low\s*[-–]\s*high', re.IGNORECASE)

# Flag pattern
FLAG_PATTERN = re.compile(r'\b(High|Low|H|L|↑|↓)\b', re.IGNORECASE)

def tag_panels_rule_first(lines: List[Dict]) -> List[Dict]:
    """Mark SECTION_PANEL using lexicons and regexes"""
    tagged_lines = []
    
    for line in lines:
        text = line.get('text', '').strip()
        is_bold = line.get('isBold', line.get('is_bold', False))
        y_norm = line.get('yNorm', line.get('y_norm', 0.5))
        
        line_copy = line.copy()
        
        # Check if line matches panel header pattern and is bold or uppercase
        if PANEL_PATTERNS.search(text) and (is_bold or text.isupper()):
            line_copy['predicted_role'] = 'SECTION_PANEL'
            line_copy['rule_confidence'] = 0.9
        # Check for TEST_ROW using existing pattern
        elif _is_test_row(text):
            line_copy['predicted_role'] = 'TEST_ROW'
            line_copy['rule_confidence'] = 0.8
        # Check for page headers/footers
        elif 'page' in text.lower() or text.startswith(('Page', 'PAGE')):
            if y_norm > 0.9:
                line_copy['predicted_role'] = 'PAGE_HEADER'
            else:
                line_copy['predicted_role'] = 'PAGE_FOOTER'
            line_copy['rule_confidence'] = 0.8
        # Check for patient name info
        elif any(word in text.lower() for word in ['patient:', 'patient name']):
            line_copy['predicted_role'] = 'HEADER_PATIENT_NAME'
            line_copy['rule_confidence'] = 0.7
        # Check for patient demographic info
        elif any(word in text.lower() for word in ['dob:', 'date of birth', 'sex:', 'mrn:']):
            line_copy['predicted_role'] = 'HEADER_PATIENT_DEMO'
            line_copy['rule_confidence'] = 0.7
        # Check for patient contact info
        elif any(word in text.lower() for word in ['address:', 'phone:', 'street', 'city']):
            line_copy['predicted_role'] = 'HEADER_PATIENT_CONTACT'
            line_copy['rule_confidence'] = 0.7
        # Check for ordering provider info
        elif any(word in text.lower() for word in ['ordering', 'physician', 'doctor', 'provider']):
            line_copy['predicted_role'] = 'HEADER_ORDERING'
            line_copy['rule_confidence'] = 0.7
        # Check for lab facility info
        elif any(word in text.lower() for word in ['laboratory', 'lab:', 'clia:', 'performing']):
            line_copy['predicted_role'] = 'HEADER_LAB'
            line_copy['rule_confidence'] = 0.7
        # Check for specimen info
        elif any(word in text.lower() for word in ['specimen', 'collected', 'accession']):
            line_copy['predicted_role'] = 'HEADER_SPECIMEN'
            line_copy['rule_confidence'] = 0.7
        # Check for comments (lines with just text, no values)
        elif text and not re.search(r'\d+\.?\d*', text):
            line_copy['predicted_role'] = 'COMMENT'
            line_copy['rule_confidence'] = 0.5
        # Check for misc sections
        elif text.isupper() and len(text) > 5:
            line_copy['predicted_role'] = 'SECTION_MISC'
            line_copy['rule_confidence'] = 0.6
        else:
            # Default to JUNK instead of OTHER
            line_copy['predicted_role'] = 'JUNK'
            line_copy['rule_confidence'] = 0.1
            
        tagged_lines.append(line_copy)
    
    return tagged_lines

def tag_testrows_rule_first(lines: List[Dict]) -> List[Dict]:
    """Mark TEST_ROW + coarse fields using enhanced rule-based NER"""
    tagged_lines = []
    
    for line in lines:
        text = line.get('text', '').strip()
        line_copy = line.copy()
        
        if _is_test_row(text):
            line_copy['predicted_role'] = 'TEST_ROW'
            line_copy['rule_confidence'] = 0.8
            
            # Extract coarse fields using enhanced NER
            parsed = _parse_test_row_fields(text)
            line_copy.update(parsed)
            
            # Mark as successfully parsed if we got a test name and value
            line_copy['parsed'] = bool(parsed.get('test_name') and parsed.get('result_value'))
        else:
            # Use JUNK instead of OTHER to match standard taxonomy
            line_copy['predicted_role'] = line.get('predicted_role', 'JUNK')
            line_copy['rule_confidence'] = 0.2
            line_copy['parsed'] = False
            
        tagged_lines.append(line_copy)
    
    return tagged_lines

def apply_header_footer_quarantine(lines: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Quarantine headers and footers that repeat across pages"""
    if len(lines) < 10:
        return lines, []
    
    # Group lines by page
    pages = {}
    for line in lines:
        page = line.get('page', 1)
        if page not in pages:
            pages[page] = []
        pages[page].append(line)
    
    if len(pages) < 2:
        return lines, []  # Need at least 2 pages
    
    # Find potential header/footer candidates (top/bottom 10%)
    candidates = []
    for page_lines in pages.values():
        for line in page_lines:
            y_norm = line.get('yNorm', line.get('y_norm', 0.5))
            if y_norm > 0.9 or y_norm < 0.1:  # Top/bottom 10%
                candidates.append(line)
    
    # Find repeating patterns across pages
    quarantined = set()
    
    for i, candidate in enumerate(candidates):
        if id(candidate) in quarantined:
            continue
            
        candidate_text = candidate.get('text', '').strip().lower()
        candidate_page = candidate.get('page', 1)
        candidate_y = candidate.get('yNorm', candidate.get('y_norm', 0.5))
        
        # Skip likely panel headers
        if _is_likely_panel_header(candidate_text):
            continue
        
        matches = [candidate]
        
        for other in candidates[i+1:]:
            if id(other) in quarantined:
                continue
                
            other_page = other.get('page', 1)
            if other_page == candidate_page:
                continue
                
            other_text = other.get('text', '').strip().lower()
            other_y = other.get('yNorm', other.get('y_norm', 0.5))
            
            # Check similarity and position
            similarity = _text_similarity(candidate_text, other_text)
            position_diff = abs(candidate_y - other_y)
            
            if similarity >= 0.8 and position_diff < 0.1:
                matches.append(other)
        
        # If found on >= 2 pages, quarantine all matches
        if len(set(match.get('page', 1) for match in matches)) >= 2:
            for match in matches:
                quarantined.add(id(match))
    
    # Separate quarantined from body
    body = [line for line in lines if id(line) not in quarantined]
    quarantined_lines = [line for line in lines if id(line) in quarantined]
    
    return body, quarantined_lines

def _is_test_row(text: str) -> bool:
    """Check if text looks like a test row"""
    # Primary check: number + unit pattern
    if TEST_ROW_PATTERN.search(text):
        return True
    
    # Secondary check: test names from lexicons with numeric content
    text_lower = text.lower()
    for test_group in TEST_NAMES.values():
        for test_name in test_group:
            if test_name in text_lower:
                # Must have some numeric content nearby
                if re.search(r'\d+\.?\d*', text):
                    return True
    
    return False

def _parse_test_row_fields(text: str) -> Dict:
    """Extract coarse fields from test row text using rule-based NER"""
    parsed = {}
    
    # Find first value (allowing comparison operators)
    value_match = VALUE_PATTERN.search(text)
    if not value_match:
        return parsed
    
    value_start = value_match.start()
    value_end = value_match.end()
    
    # Name = leading text before first numeric
    name = text[:value_start].strip()
    if name:
        parsed['test_name'] = name
    
    # Value = first numeric (with any comparison operators)
    parsed['result_value'] = value_match.group().strip()
    
    # Unit = next token matching whitelist after value
    remaining_text = text[value_end:]
    unit_match = UNITS_PATTERN.search(remaining_text[:20])  # Look within 20 chars
    if unit_match:
        parsed['unit'] = unit_match.group()
        unit_end = value_end + unit_match.end()
        remaining_text = text[unit_end:]
    
    # Reference range = any A–B or low–high pattern at end
    ref_match = REF_RANGE_PATTERN.search(text)
    if ref_match:
        parsed['reference_range'] = ref_match.group().strip()
    
    # Flags = High|Low|H|L|↑|↓ if present
    flags = []
    for flag_match in FLAG_PATTERN.finditer(text):
        flags.append(flag_match.group())
    if flags:
        parsed['flags'] = flags
    
    return parsed

def _text_similarity(text1: str, text2: str) -> float:
    """Calculate word-based similarity between two texts"""
    if not text1 or not text2:
        return 0.0
    
    if text1 == text2:
        return 1.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)

def _is_likely_panel_header(text: str) -> bool:
    """Check if text looks like a panel header that shouldn't be quarantined"""
    return bool(PANEL_PATTERNS.search(text))