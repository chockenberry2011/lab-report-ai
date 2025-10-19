"""
Canonical corrections field schema and resolver.

This registry lets the backend accept multiple frontend aliases (dotted or JSON-pointer
paths) and normalize them into canonical field keys used during application.
"""
from typing import Dict, List, Optional, Set

# Central registry: canonical_key -> list of accepted aliases
FIELD_MAP: Dict[str, List[str]] = {
    # Organization / Vendor
    "vendor_name": ["vendor.name", "/vendor/name", "payee.name"],

    # Patient
    "patient_first_name": ["patient.first_name", "/patient/first_name"],
    "patient_last_name": ["patient.last_name", "/patient/last_name"],

    # Test-row canonical fields (legacy supported already)
    "test_name": ["test_name"],
    "result_value": ["result_value"],
    "units": ["units"],
    "reference_range": ["reference_range"],
    "flag": ["flag"],
    # Header legacy helpers
    "header_label": ["header_label"],
    "header_value": ["header_value"],
}

# Fields that must not be empty on replacement (business rule)
REQUIRED_FIELDS: Set[str] = {
    "vendor_name",
}

def resolve_field(field: str) -> Optional[str]:
    """Resolve an incoming field key to its canonical key.

    - If already canonical, return as-is.
    - Else, scan aliases and return canonical if matched.
    - Else, return None.
    """
    if not field:
        return None
    if field in FIELD_MAP:
        return field
    # normalize form (strip leading JSON-pointer root, common whitespace)
    needle = field.strip()
    for canonical, aliases in FIELD_MAP.items():
        if needle == canonical:
            return canonical
        for alias in aliases:
            if needle == alias:
                return canonical
    return None

