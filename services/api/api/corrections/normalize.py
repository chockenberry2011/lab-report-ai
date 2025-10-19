"""
Utilities to normalize corrections entries on disk for migrations.

- Canonicalize field keys via resolve_field
- Ensure value is set (prefer new_value if value empty)
"""
from typing import Dict, Any, List, Tuple

from api.corrections.schema import resolve_field


def _is_empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def normalize_correction_item(item: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """Return (normalized_item, stats_delta). Does not mutate input.

    Stats keys: canonicalized, value_filled, unknown_fields
    """
    c = dict(item)
    stats = {"canonicalized": 0, "value_filled": 0, "unknown_fields": 0}

    # Value normalization: prefer new_value if value is empty
    if _is_empty(c.get("value")) and not _is_empty(c.get("new_value")):
        c["value"] = c.get("new_value")
        stats["value_filled"] += 1

    # Field canonicalization only when 'field' is provided and no explicit 'path'
    fld = c.get("field")
    if isinstance(fld, str) and not c.get("path"):
        canon = resolve_field(fld)
        if canon:
            if canon != fld:
                stats["canonicalized"] += 1
            c["field"] = canon
        else:
            stats["unknown_fields"] += 1

    return c, stats


def normalize_items(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    out: List[Dict[str, Any]] = []
    total = {"canonicalized": 0, "value_filled": 0, "unknown_fields": 0}
    for it in items or []:
        norm, delta = normalize_correction_item(it)
        out.append(norm)
        for k, v in delta.items():
            total[k] = total.get(k, 0) + v
    return out, total

