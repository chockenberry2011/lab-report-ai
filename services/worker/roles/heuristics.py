"""
Heuristic rules for detecting TEST_ROW lines when the ML model produces insufficient results.

This module provides fallback logic to identify test result rows based on textual patterns
that are commonly found in lab reports, such as units, reference ranges, and flags.
"""

import re
from typing import List, Dict, Set, Any


# Common lab units (case-insensitive)
UNIT_HINTS = [
    "mg/dL", "g/dL", "mmol/L", "mm/hr", "x10", "IU/L", "U/L", "mIU/L", 
    "ng/mL", "pg/mL", "%", "/uL", "/µL", "/L", "fL", "g/L"
]

# Common lab flags
FLAG_TOKENS = ["H", "L", "LOW", "HIGH", "CRITICAL", "ABNORMAL"]

# Reference range pattern (e.g., "70-100", "2.5 - 4.0", "1.2–3.5")
REFERENCE_RANGE_PATTERN = re.compile(r'\b\d+(\.\d+)?\s*[-–]\s*\d+(\.\d+)?\b')

# Pattern to detect digits in text
DIGIT_PATTERN = re.compile(r'\d')


def tag_rows_heuristic(merged_lines: List[Dict[str, Any]]) -> Set[int]:
    """
    Apply heuristic rules to identify TEST_ROW lines from merged line data.
    
    Args:
        merged_lines: List of merged line dictionaries with 'text' and other fields
        
    Returns:
        Set of line indexes that should be tagged as TEST_ROW
    """
    test_row_indexes = set()
    
    for i, line in enumerate(merged_lines):
        if _is_test_row_heuristic(line):
            test_row_indexes.add(i)
    
    return test_row_indexes


def _is_test_row_heuristic(line: Dict[str, Any]) -> bool:
    """
    Check if a single merged line should be tagged as TEST_ROW based on heuristic rules.
    
    Args:
        line: Merged line dictionary with 'text' field
        
    Returns:
        True if line should be tagged as TEST_ROW
    """
    text = line.get('text', '').strip()
    if not text:
        return False
    
    # Don't override SECTION_PANEL lines
    current_role = line.get('predicted_role', '')
    if current_role == 'SECTION_PANEL':
        return False
    
    # Check for disclaimer/paragraph exclusion
    # (>= 12 words without tabs and no units or range)
    if _is_disclaimer_paragraph(text):
        return False
    
    # Rule 1: Has digit AND unit hints
    if _has_digit_and_units(text):
        return True
    
    # Rule 2: Contains reference range pattern
    if _has_reference_range(text):
        return True
    
    # Rule 3: Has flag tokens and numbers
    if _has_flags_and_numbers(text):
        return True
    
    return False


def _is_disclaimer_paragraph(text: str) -> bool:
    """Check if text looks like a disclaimer/paragraph that should be excluded."""
    words = text.split()
    
    # Must be >= 12 words
    if len(words) < 12:
        return False
    
    # Must not contain tabs (not tabular data)
    if '\t' in text:
        return False
    
    # Must not contain units or reference ranges
    if _has_units(text) or _has_reference_range(text):
        return False
    
    return True


def _has_digit_and_units(text: str) -> bool:
    """Check if text has both digits and unit hints."""
    if not DIGIT_PATTERN.search(text):
        return False
    
    return _has_units(text)


def _has_units(text: str) -> bool:
    """Check if text contains any unit hints (case-insensitive)."""
    text_lower = text.lower()
    return any(unit.lower() in text_lower for unit in UNIT_HINTS)


def _has_reference_range(text: str) -> bool:
    """Check if text contains a reference range pattern."""
    return REFERENCE_RANGE_PATTERN.search(text) is not None


def _has_flags_and_numbers(text: str) -> bool:
    """Check if text has both flag tokens and numbers."""
    if not DIGIT_PATTERN.search(text):
        return False
    
    # Check for flag tokens (case-insensitive word boundaries)
    text_upper = text.upper()
    for flag in FLAG_TOKENS:
        # Use word boundaries to avoid matching parts of other words
        if re.search(rf'\b{re.escape(flag)}\b', text_upper):
            return True
    
    return False