"""
Rule-based parsing for single test rows.

Logic:
  NAME (greedy but trimmed)
  VALUE (supports optional comparators like <,<=,>,>=)
  optional FLAG token (H|HIGH|L|LOW|ABN|ABNORMAL|CRIT|CRITICAL|ALERT, case-insensitive)
  optional UNIT (tokens like mg/dL, mmol/L, mL/min/1.73, x10E3/uL, %, IU/L, ng/mL)
  optional REF_RANGE (e.g., 70-99, 4.0–10.5, 0.3 - 4.7)
  
Enhanced parsing handles flags appearing between result values and units with fallback logic.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .units import coerce_unit, unit_is_allowed

_DASH = r"[-–—]"
_CMP = r"(?:(?:<=|>=|<|>)\s*)?"
_NUM = r"\d+(?:\.\d+)?"
_RANGE = rf"(?:<?\s*{_NUM}\s*{_DASH}\s*>?\s*{_NUM})"

# Enhanced unit pattern to handle complex units like mL/min/1.73
_UNIT_TOKEN = r"[A-Za-z%/\^\d\.]+(?:/[A-Za-z%\^\d\.]+)*"
# Enhanced flag pattern to include more flag types (case-insensitive) - order matters!
_FLAG_TOKEN = r"(?:HIGH|LOW|ABNORMAL|CRITICAL|ALERT|ABN|CRIT|H|L)"

_PRIMARY_RE = re.compile(
    rf"^\s*(?P<name>.+?)\s+"
    rf"(?P<value>{_CMP}{_NUM})"  # value with optional comparator
    rf"(?:\s+(?P<flag>{_FLAG_TOKEN}))?"  # optional flag
    rf"(?:\s+(?P<unit>{_UNIT_TOKEN}))?"  # optional unit
    rf"(?:\s+(?P<range>{_RANGE}))?"  # optional reference range
    rf"(?:\s+.*)?",  # allow trailing data
    re.IGNORECASE
)


def _norm_flag(flag: Optional[str]) -> Optional[str]:
    """Normalize flag tokens to standard format."""
    if not flag:
        return None
    f = flag.strip().upper()
    if f in {"HIGH", "H"}:
        return "HIGH"
    if f in {"LOW", "L"}:
        return "LOW"
    if f in {"ABN", "ABNORMAL"}:
        return "ABNORMAL"
    if f in {"CRIT", "CRITICAL"}:
        return "CRITICAL"
    if f == "ALERT":
        return "ALERT"
    return None


def _is_flag_token(token: Optional[str]) -> bool:
    """Check if a token is a recognized flag."""
    if not token:
        return False
    return _norm_flag(token) is not None


def _is_unit_like(token: Optional[str]) -> bool:
    """Check if a token looks like a unit (contains letters, %, /, etc.)."""
    if not token:
        return False
    # Units should contain letters or common unit symbols
    return bool(re.search(r'[A-Za-z%/\^\.]', token))


def _tokenize_remaining(text: str) -> List[str]:
    """Split remaining text into tokens for post-parse analysis."""
    return [t.strip() for t in text.split() if t.strip()]


def parse_line(text: str) -> Dict[str, object]:
    """
    Enhanced parsing that handles flags appearing between result values and units.
    
    Implementation strategy:
    1) Extract numeric value using regex
    2) Tokenize remaining text and process sequentially
    3) Look for flag tokens immediately after numeric value
    4) Look for unit tokens after flag (or after value if no flag)
    5) Post-parse repair: if units contain flag tokens, move to flag and find next unit
    """
    s = text or ""
    fields: Dict[str, object] = {
        "test_name": None,
        "result_value": None,
        "units": None,
        "reference_range": None,
        "flags": [],
    }
    warnings: List[str] = []

    # First try the primary regex for well-formed cases
    m = _PRIMARY_RE.match(s)
    
    if m:
        name = (m.group("name") or "").strip()
        value = (m.group("value") or "").strip()
        flag = _norm_flag(m.group("flag"))
        unit = (m.group("unit") or "").strip() or None
        ref_range = (m.group("range") or "").replace(" ", "").strip() or None
        
        # Post-parse repair: check if units is actually a flag token
        if unit and _is_flag_token(unit) and not flag:
            flag = _norm_flag(unit)
            unit = None
            
            # Try to find the next unit-like token in remaining text
            # Extract everything after the matched portion to look for additional tokens
            full_match = m.group(0)
            remaining_start = len(full_match.rstrip())
            if remaining_start < len(s):
                remaining_tokens = _tokenize_remaining(s[remaining_start:])
                for token in remaining_tokens:
                    if _is_unit_like(token) and not _is_flag_token(token):
                        unit = token
                        break
    else:
        # Fallback parsing for complex cases
        # Extract test name and numeric value manually
        value_pattern = re.compile(rf"({_CMP}{_NUM})")
        value_match = value_pattern.search(s)
        
        if not value_match:
            return {"parsed_fields": fields}
            
        value_start = value_match.start()
        value_end = value_match.end()
        
        name = s[:value_start].strip()
        value = value_match.group(1)
        
        # Tokenize everything after the numeric value
        remaining_text = s[value_end:].strip()
        tokens = _tokenize_remaining(remaining_text)
        
        flag = None
        unit = None
        ref_range = None
        
        # Process tokens sequentially
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            # Check for flag first
            if not flag and _is_flag_token(token):
                flag = _norm_flag(token)
                i += 1
                continue
                
            # Check for unit
            if not unit and _is_unit_like(token) and not _is_flag_token(token):
                unit = token
                i += 1
                continue
                
            # Check for reference range
            if not ref_range and re.match(_RANGE, token):
                ref_range = token.replace(" ", "")
                i += 1
                continue
                
            # Skip unrecognized tokens
            i += 1

    # Coerce/normalize unit if possible
    if unit:
        unit, reason = coerce_unit(name, unit)
        if reason:
            warnings.append(f"unit_coerced:{reason}")

        # Unit sanity check
        if not unit_is_allowed(name, unit):
            warnings.append("unit_unlikely_for_test")

    fields.update(
        {
            "test_name": name or None,
            "result_value": value or None,
            "units": unit,
            "reference_range": ref_range,
            "flags": [flag] if flag else [],
        }
    )

    out: Dict[str, object] = {"parsed_fields": fields}
    if warnings:
        out["fieldWarnings"] = warnings
    return out

