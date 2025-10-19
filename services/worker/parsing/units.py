"""
Utilities for Test-Row unit handling and sanity checks.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

# Minimal allowed unit map for common CBC/CMP analytes. Extend as needed.
ALLOWED_UNITS: Dict[str, Set[str]] = {
    # Hematology
    "WBC": {"x10E3/uL", "10^3/uL", "10e3/uL"},
    "RBC": {"x10E6/uL", "10^6/uL", "10e6/uL"},
    "HGB": {"g/dL"},
    "HCT": {"%"},
    "PLT": {"x10E3/uL", "10^3/uL", "10e3/uL"},
    # Chemistry examples
    "GLUCOSE": {"mg/dL", "mmol/L"},
    "SODIUM": {"mmol/L"},
    "POTASSIUM": {"mmol/L"},
    "TSH": {"uIU/mL", "mIU/L"},
}


def _canon(test_name: Optional[str]) -> str:
    return (test_name or "").strip().upper()


def _normalize_unit_format(unit: str) -> str:
    """Normalize common exponent formats to a canonical caret notation."""
    u = (unit or "").strip()
    # Normalize various exponent spellings to caret form
    u = u.replace("x10E3/uL", "10^3/uL").replace("x10e3/uL", "10^3/uL")
    u = u.replace("10e3/uL", "10^3/uL")
    u = u.replace("x10E6/uL", "10^6/uL").replace("x10e6/uL", "10^6/uL")
    u = u.replace("10e6/uL", "10^6/uL")
    return u


def coerce_unit(test_name: Optional[str], unit: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt to coerce/normalize the unit for a given test name.

    Returns (possibly corrected_unit, reason) where reason is a short string when a change was applied.
    If no change, returns (unit, None).
    """
    if not unit:
        return unit, None
    normalized = _normalize_unit_format(unit)
    if normalized != unit:
        return normalized, "normalized_exponent_format"
    return unit, None


def unit_is_allowed(test_name: Optional[str], unit: Optional[str]) -> bool:
    if not test_name or not unit:
        return True
    allowed = ALLOWED_UNITS.get(_canon(test_name))
    if not allowed:
        return True
    return unit in allowed

