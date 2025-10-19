"""
Corrections service for loading and applying corrections to compose documents.

This module handles:
1. Loading corrections from the file system
2. Normalizing correction keys to JSONPointer-like paths
3. Applying corrections to compose documents before serving to viewers
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import os

from api.exceptions import CorrectionsFileFormatError

logger = logging.getLogger("api")

# Lightweight instrumentation (no PHI). Tracks last N apply events.
from collections import deque
from datetime import datetime, timezone

_LAST_APPLY_COUNT: int = 0
_APPLY_EVENTS = deque(maxlen=100)

def get_last_apply_count() -> int:
    return _LAST_APPLY_COUNT

def record_apply_event(result_id: str, total: int, applied: int):
    """Record a non-PHI event for health/diagnostics."""
    _APPLY_EVENTS.append({
        "result_id": result_id,
        "total": int(total),
        "applied": int(applied),
        "ts": datetime.now(timezone.utc).isoformat(),
    })

def get_apply_events(limit: int = 20):
    items = list(_APPLY_EVENTS)[-limit:]
    return items

def load_corrections(result_id: str) -> Dict[str, Any]:
    """
    Load corrections for a result ID and return as a normalized dict.
    
    Args:
        result_id: The result ID (with or without debug suffixes)
        
    Returns:
        Dict mapping JSONPointer-like paths to correction values
        
    Example:
        {
            "lab_panels.0.test_rows.2.result_value": "72",
            "lab_panels.0.test_rows.2.units": "mg/dL",
            "lab_panels.0.test_rows.2.flag": "HIGH"
        }
    """
    base_dir = os.getenv("RESULTS_DIR", "/data/results")
    corrections_file = Path(base_dir) / result_id / "corrections.json"
    rid = result_id.split(".", 1)[0]
    
    if not corrections_file.exists():
        logger.debug("corrections_load_missing", extra={"rid": rid, "path": str(corrections_file)})
        return {}
    
    try:
        with open(corrections_file, "r", encoding="utf-8") as f:
            corrections_list = json.load(f)

        found_type = type(corrections_list).__name__
        logger.info("corrections_load", extra={"rid": rid, "path": str(corrections_file), "type": found_type})

        if not isinstance(corrections_list, list):
            logger.error(
                "corrections_load_wrong_type expected=array found=%s",
                found_type,
                extra={"rid": rid, "path": str(corrections_file)},
            )
            raise CorrectionsFileFormatError(
                result_id=rid,
                file_path=str(corrections_file),
                expected_type="array",
                found_type=found_type,
            )
        
        # Convert array format to dict keyed by JSONPointer paths
        corrections_dict = {}
        for correction in corrections_list:
            if not isinstance(correction, dict):
                continue
                
            field = correction.get("field")
            new_value = correction.get("new_value")
            line_number = correction.get("line_number")
            
            if not field:
                continue
            
            # Generate JSONPointer-like path based on field and line_number
            path = _generate_correction_path(field, line_number, correction)
            if path:
                corrections_dict[path] = new_value
        
        logger.info("corrections_loaded", extra={"rid": rid, "path": str(corrections_file), "count": len(corrections_dict)})
        return corrections_dict
        
    except Exception as e:
        logger.error("corrections_load_error %s", str(e), extra={"rid": rid, "path": str(corrections_file)})
        return {}


def _generate_correction_path(field: str, line_number: Optional[int], correction: Dict[str, Any]) -> Optional[str]:
    """
    Generate a JSONPointer-like path for a correction field.
    
    This maps field names to document structure paths.
    """
    # Map common field names to document paths
    field_mappings = {
        "test_name": "test_name",
        "result_value": "result_value", 
        "units": "units",
        "reference_range": "reference_range",
        "flag": "flag",
        "header_label": "label",
        "header_value": "value",
        # Canonical document-info fields
        "vendor_name": "vendor_name",
        "patient_first_name": "patient_first_name",
        "patient_last_name": "patient_last_name",
    }
    
    if field not in field_mappings:
        logger.debug("Unknown field '%s' in correction, skipping", field)
        return None
    
    mapped_field = field_mappings[field]
    
    # For header fields, use a different path structure
    if field.startswith("header_"):
        # This would need more sophisticated mapping based on actual document structure
        # For now, return a generic path
        return f"document_info.{mapped_field}"
    # Canonical document-info fields (no line number)
    if field in ("vendor_name", "patient_first_name", "patient_last_name"):
        return f"document_info.{mapped_field}"
    
    # For test row fields, we need to find the test row by line_number
    # Since we don't have the document structure here, we'll use a generic pattern
    # The apply_corrections function will need to resolve this to actual array indices
    if line_number:
        return f"test_rows.line_{line_number}.{mapped_field}"
    else:
        # Fallback for corrections without line numbers
        return f"test_rows.unknown.{mapped_field}"


def apply_corrections(compose_doc: Dict[str, Any], corrections: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply corrections to a compose document.
    
    Args:
        compose_doc: The original compose document
        corrections: Dict mapping paths to correction values
        
    Returns:
        Updated compose document with corrections applied
    """
    if not corrections:
        logger.debug("No corrections to apply")
        return compose_doc
    
    # Make a deep copy to avoid modifying the original
    import copy
    updated_doc = copy.deepcopy(compose_doc)
    
    applied_count = 0
    
    for path, value in corrections.items():
        try:
            if _apply_single_correction(updated_doc, path, value):
                applied_count += 1
        except Exception as e:
            logger.warning("Failed to apply correction at path '%s': %s", path, str(e))
    
    # Update last-applied counter for callers to inspect; avoid logging PHI here
    global _LAST_APPLY_COUNT
    _LAST_APPLY_COUNT = applied_count
    logger.info("Applied %d correction(s) to compose document", applied_count)
    return updated_doc


def _apply_single_correction(doc: Dict[str, Any], path: str, value: Any) -> bool:
    """
    Apply a single correction to the document.
    
    Returns True if the correction was successfully applied.
    """
    try:
        # Handle different path patterns
        if path.startswith("test_rows.line_"):
            return _apply_test_row_correction(doc, path, value)
        elif path.startswith("document_info."):
            return _apply_document_info_correction(doc, path, value)
        else:
            logger.debug("Unknown correction path pattern: %s", path)
            return False
    except Exception as e:
        logger.warning("Error applying correction at path '%s': %s", path, str(e))
        return False


def _apply_test_row_correction(doc: Dict[str, Any], path: str, value: Any) -> bool:
    """
    Apply a correction to a test row by finding it by line number.
    
    Path format: test_rows.line_{line_number}.{field}
    """
    try:
        # Parse the path: test_rows.line_123.result_value
        parts = path.split(".")
        if len(parts) != 3 or not parts[1].startswith("line_"):
            return False
        
        line_number_str = parts[1][5:]  # Remove "line_" prefix
        line_number = int(line_number_str)
        field_name = parts[2]
        
        # Find the test row with matching line number
        lab_panels = doc.get("lab_panels", [])
        for panel in lab_panels:
            if not isinstance(panel, dict):
                continue
            
            test_rows = panel.get("test_rows", [])
            for test_row in test_rows:
                if not isinstance(test_row, dict):
                    continue
                
                if test_row.get("line_number") == line_number:
                    # Apply the correction
                    old_value = test_row.get(field_name)
                    test_row[field_name] = value
                    logger.debug("Applied correction: line %d, field '%s': '%s' -> '%s'", 
                               line_number, field_name, old_value, value)
                    return True
        
        logger.debug("No test row found with line_number %d for correction", line_number)
        return False
        
    except (ValueError, KeyError, IndexError) as e:
        logger.debug("Failed to parse test row correction path '%s': %s", path, str(e))
        return False


def _apply_document_info_correction(doc: Dict[str, Any], path: str, value: Any) -> bool:
    """
    Apply a correction to document info fields.
    
    Path format: document_info.{field}
    """
    try:
        # Parse the path: document_info.field_name
        parts = path.split(".", 1)
        if len(parts) != 2:
            return False
        
        field_name = parts[1]
        
        # Ensure document_info exists
        if "document_info" not in doc:
            doc["document_info"] = {}
        
        # Apply the correction
        old_value = doc["document_info"].get(field_name)
        doc["document_info"][field_name] = value
        logger.debug("Applied document_info correction: field '%s': '%s' -> '%s'", 
                   field_name, old_value, value)
        return True
        
    except Exception as e:
        logger.debug("Failed to apply document_info correction '%s': %s", path, str(e))
        return False


def get_corrections_summary(result_id: str) -> Dict[str, Any]:
    """
    Get a summary of corrections for a result ID.
    
    Returns:
        Dict with correction counts and metadata
    """
    corrections = load_corrections(result_id)
    
    # Count corrections by type
    test_row_corrections = 0
    document_info_corrections = 0
    
    for path in corrections.keys():
        if path.startswith("test_rows."):
            test_row_corrections += 1
        elif path.startswith("document_info."):
            document_info_corrections += 1
    
    return {
        "total_corrections": len(corrections),
        "test_row_corrections": test_row_corrections,
        "document_info_corrections": document_info_corrections,
        "has_corrections": len(corrections) > 0
    }
