from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import os
import json
import logging

from api.utils.ids import normalize_result_id
from api.utils.corrections import set_by_path, unset_by_path

logger = logging.getLogger("api")

DATA_ROOT = Path(os.environ.get("DATA_DIR", "/data"))
OUTBOX = DATA_ROOT / "outbox"
RESULTS_DIR = DATA_ROOT / "results"
OUTBOX.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _canonical_path(rid: str) -> Path:
    rid = normalize_result_id(rid)
    d = RESULTS_DIR / rid
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{rid}.json"


def _bootstrap_canonical(rid: str) -> Path:
    """Ensure canonical <RID>.json exists; create from best available source.

    Returns Path to canonical file.
    """
    rid = normalize_result_id(rid)
    cpath = _canonical_path(rid)
    if cpath.exists():
        return cpath
    # Prefer compose debug if present, else fallback to outbox <rid>.json
    compose_path = OUTBOX / f"{rid}.03_compose.debug.json"
    alt_path = OUTBOX / f"{rid}.json"
    for p in (compose_path, alt_path):
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            cpath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("canonical_bootstrap_ok base_id=%s from=%s target=%s", rid, str(p), str(cpath))
            return cpath
    # If nothing found, initialize a minimal document
    minimal = {"document_info": {}, "lab_panels": []}
    cpath.write_text(json.dumps(minimal, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("canonical_bootstrap_minimal base_id=%s target=%s", rid, str(cpath))
    return cpath


def _load_corrections_list(rid: str) -> List[Dict[str, Any]]:
    rid = normalize_result_id(rid)
    p = RESULTS_DIR / rid / "corrections.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        return data.get("corrections") or data.get("items") or []
    except Exception:
        return []


def _apply_correction(rid: str, item: Dict[str, Any]) -> int:
    """Apply a single correction item to canonical doc; returns 1 if applied else 0."""
    rid = normalize_result_id(rid)
    cpath = _bootstrap_canonical(rid)
    try:
        doc = json.loads(cpath.read_text(encoding="utf-8"))
    except Exception:
        doc = {"document_info": {}, "lab_panels": []}

    op = (item.get("op") or "replace").lower()
    value = item.get("value")
    path = item.get("path")
    if not path:
        fld = item.get("field")
        if isinstance(fld, str):
            if fld.startswith("header_"):
                mapped = "label" if fld == "header_label" else "value"
                path = f"document_info.{mapped}"
            elif fld in ("vendor_name", "patient_first_name", "patient_last_name"):
                path = f"document_info.{fld}"
            elif fld in ("test_name", "result_value", "units", "reference_range", "flag"):
                # For lab panel fields without path context, we cannot apply them
                # These should be saved with path context like "lab_panels.0.test_rows.1.test_name"
                return 0
    if not path:
        return 0
    try:
        if op == "unset":
            unset_by_path(doc, path)
        else:
            set_by_path(doc, path, value)
        cpath.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1
    except Exception:
        return 0

