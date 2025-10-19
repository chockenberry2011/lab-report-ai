# services/api/results.py
from pathlib import Path
import json
import os
import datetime
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Request, Body
import tempfile
import shutil
from pydantic import BaseModel
from api.serializers import serialize_lab_result, EnhancedLabResult
from api.utils.ids import normalize_result_id
from .services.results_io import (
    _canonical_path,
    _bootstrap_canonical,
    _load_corrections_list,
    _apply_correction,
)
from api.exceptions import CorrectionsFileFormatError

router = APIRouter()

# Setup logging
logger = logging.getLogger("api")

DATA_ROOT = Path(os.environ.get("DATA_DIR", "/data"))
OUTBOX = DATA_ROOT / "outbox"
OUTBOX.mkdir(parents=True, exist_ok=True)
RESULTS_DIR = DATA_ROOT / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


## normalize_result_id now provided by utils.ids


def _row_from_file(p: Path) -> Dict[str, Any]:
    st = p.stat()
    stem = p.stem
    base_id = stem.split(".", 1)[0]
    cpath = _canonical_path(base_id)
    # Known debug variants
    debug_candidates = [
        OUTBOX / f"{base_id}.01_lines.debug.json",
        OUTBOX / f"{base_id}.01a_lines_merged.debug.json",
        OUTBOX / f"{base_id}.02_roles.debug.json",
        OUTBOX / f"{base_id}.03_compose.debug.json",
    ]
    item = {
        "job_id": stem,
        "rid": base_id,
        "filename": p.name,
        "modified": st.st_mtime,
        "size": st.st_size,
        "needsReview": False,
        "summary": None,
        "has_canonical": cpath.exists(),
        "canonical_path": str(cpath) if cpath.exists() else None,
        "debug_paths": [str(x) for x in debug_candidates if x.exists()],
    }
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        item["needsReview"] = bool(data.get("needsReview"))
        item["summary"] = data.get("summary")
    except Exception:
        pass
    return item

@router.get("/results")
def list_results(page: int = 1, per_page: int = 50, q: Optional[str] = None):
    page = max(1, page)
    per_page = max(1, min(per_page, 200))
    files: List[Path] = sorted(
        OUTBOX.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if q:
        ql = q.lower()
        files = [p for p in files if ql in p.name.lower() or ql in p.stem.lower()]
    total = len(files)
    start = (page - 1) * per_page
    end = start + per_page
    items = [_row_from_file(p) for p in files[start:end]]
    return {
        "results": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_next": end < total,
    }

def _read_canonical(base_id: str) -> Dict[str, Any]:
    cpath = _canonical_path(base_id)
    if not cpath.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    try:
        return json.loads(cpath.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read result: {e}")

@router.get("/results/{job_id}")
def get_result(job_id: str):
    try:
        base_id = normalize_result_id(job_id)
        if base_id != job_id:
            logger.warning("Incoming result id normalized: '%s' -> '%s'", job_id, base_id)

        # Bootstrap canonical if missing
        cpath = _bootstrap_canonical(base_id)
        doc = _read_canonical(base_id)

        # Load and apply corrections (sorted by ts, stable)
        corrections = _load_corrections_list(base_id)
        def _ts(c):
            return c.get("ts") or ""
        applied = 0
        for c in sorted(corrections, key=_ts):
            # Apply in-memory to avoid N writes
            op = (c.get("op") or "replace").lower()
            value = c.get("value")
            path = c.get("path")
            if not path:
                fld = c.get("field")
                if isinstance(fld, str):
                    if fld.startswith("header_"):
                        mapped = "label" if fld == "header_label" else "value"
                        path = f"document_info.{mapped}"
                    elif fld in ("vendor_name", "patient_first_name", "patient_last_name"):
                        path = f"document_info.{fld}"
            if not path:
                continue
            try:
                if op == "unset":
                    from api.utils.corrections import unset_by_path as _unset
                    _unset(doc, path)
                else:
                    from api.utils.corrections import set_by_path as _set
                    _set(doc, path, value)
                applied += 1
            except Exception:
                pass

        # Persist canonical back if any applied
        cpath = _canonical_path(base_id)
        if applied > 0:
            cpath.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        # Emit derivative compose debug (optional)
        try:
            (OUTBOX / f"{base_id}.03_compose.debug.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        logger.info("compose_merge applied=%d target=%s", applied, str(cpath))

        # Serialize with enhanced fields for UI
        enhanced_result = serialize_lab_result(doc)
        return enhanced_result.dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read result: {e}")

@router.get("/results/{job_id}/enhanced", response_model=EnhancedLabResult)
def get_enhanced_result(job_id: str):
    """Get enhanced lab result with structured fields for manual review."""
    p = OUTBOX / f"{job_id}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    try:
        # Mirror get_result but return pydantic EnhancedLabResult instance
        base_id = normalize_result_id(job_id)
        if base_id != job_id:
            logger.warning("Incoming result id normalized: '%s' -> '%s'", job_id, base_id)
        doc = _bootstrap_canonical(base_id)
        corrections = _load_corrections_list(base_id)
        def _ts(c):
            return c.get("ts") or ""
        applied = 0
        for c in sorted(corrections, key=_ts):
            if _apply_correction(doc, c):
                applied += 1
        cpath = _canonical_path(base_id)
        if applied > 0:
            cpath.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            (OUTBOX / f"{base_id}.03_compose.debug.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        logger.info("compose_merge applied=%d target=%s", applied, str(cpath))

        return serialize_lab_result(doc)
    except HTTPException:
        raise  # Re-raise HTTP exceptions (including our 422)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read result: {e}")

@router.get("/results/{job_id}/raw")
def get_raw_result(job_id: str):
    """Get raw lab result without serialization (for debugging)."""
    p = OUTBOX / f"{job_id}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Result not found")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read result: {e}")


# Correction models
class Correction(BaseModel):
    line_number: Optional[int] = None
    field: str                    # e.g. "test_name", "result_value", "units", etc.
    new_value: Optional[str] = None
    old_value: Optional[str] = None
    reason: Optional[str] = None


# OLD CORRECTIONS ENDPOINT - REPLACED BY corrections_api.py
# @router.post("/results/{result_id}/corrections")
# async def post_corrections(result_id: str, request: Request, body: Any = Body(None)):
#     """
#     Save corrections for a result.
#
#     Accepts:
#       - New format: {"items":[{op?, path, value?}], "schema_version":1}
#       - Back-compat: {"items":[{path, value}]}  (op defaults to 'set')
#       - Legacy format: [{"field": "...", "new_value": "...", "line_number": ...}]
#     """
#     logger.info("Saving corrections for %s | content-type=%s", result_id, request.headers.get("content-type"))
#     raw_bytes = await request.body()
#     logger.info("Raw body: %s", raw_bytes.decode("utf-8", "ignore"))
#
#     # Handle clients that send JSON with text/plain or missing Content-Type
#     if body is None:
#         try:
#             body = json.loads(raw_bytes.decode("utf-8"))
#             logger.info("Fallback JSON parsing succeeded")
#         except Exception as e:
#             logger.error("Fallback JSON parsing failed: %s", str(e))
#             raise HTTPException(status_code=400, detail="Request body is not valid JSON")
#
#     base_id = normalize_result_id(result_id)
#     d = RESULTS_DIR / base_id
#     d.mkdir(parents=True, exist_ok=True)
#     p = d / "corrections.json"
#
#     try:
#         # Detect format and normalize
#         if isinstance(body, list):
#             # Legacy format: list of corrections with field/new_value/line_number
#             if body and "field" in body[0]:
#                 logger.info("Detected legacy corrections format")
#                 # Convert legacy format to new format and save to legacy location too
#                 return await _handle_legacy_corrections(result_id, body)
#             else:
#                 # New format as list (items directly)
#                 items = body
#         elif isinstance(body, dict):
#             if "items" in body:
#                 # New format with items wrapper
#                 items = body.get("items", [])
#             elif "corrections" in body:
#                 # Legacy format with corrections wrapper
#                 logger.info("Detected legacy corrections format with wrapper")
#                 return await _handle_legacy_corrections(result_id, body["corrections"])
#             else:
#                 raise HTTPException(status_code=400, detail="Unknown corrections format")
#         else:
#             raise HTTPException(status_code=400, detail="Invalid corrections payload")
#
#         # Normalize incoming ops (default op="set")
#         normalized_items = []
#         for it in items:
#             if "op" not in it:
#                 it = {"op": "set", **it}
#             normalized_items.append(it)
#
#         merged = {"items": normalized_items, "schema_version": 1}
#         p.write_text(json.dumps(merged, ensure_ascii=False, indent=2))
#         logger.info("Saved %d new-format corrections for base_id=%s", len(normalized_items), base_id)
#         return {"ok": True}
#
#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error("Failed to save corrections for %s: %s", result_id, str(e))
#         raise HTTPException(status_code=400, detail=f"Failed to save corrections: {e.__class__.__name__}: {e}")


async def _handle_legacy_corrections(result_id: str, corrections_list: List[Dict[str, Any]]):
    """Handle legacy correction format by saving to both old and new locations"""
    logger.info("Processing %d legacy corrections", len(corrections_list))
    
    # Save to legacy location (existing behavior)
    base_id = normalize_result_id(result_id)
    base_dir = os.getenv("RESULTS_DIR", "/data/results")
    legacy_dir = os.path.join(base_dir, base_id)
    os.makedirs(legacy_dir, exist_ok=True)
    legacy_path = os.path.join(legacy_dir, "corrections.json")
    
    # Load existing legacy corrections
    existing_legacy = []
    if os.path.exists(legacy_path):
        try:
            with open(legacy_path, "r", encoding="utf-8") as f:
                existing_raw = json.load(f)
                if isinstance(existing_raw, list):
                    existing_legacy = existing_raw
        except Exception as e:
            logger.warning("Failed to read existing legacy corrections: %s", str(e))
    
    # Validate and save legacy format
    validated_corrections = []
    for correction in corrections_list:
        if isinstance(correction, dict) and "field" in correction:
            validated_corrections.append(correction)
    
    merged_legacy = existing_legacy + validated_corrections
    
    # Atomic write to legacy location
    fd, tmp_path = tempfile.mkstemp(dir=legacy_dir, prefix="corrections.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(merged_legacy, f, ensure_ascii=False, indent=2)
        shutil.move(tmp_path, legacy_path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
    
    logger.info("Saved %d legacy corrections to %s", len(validated_corrections), legacy_path)
    return {"ok": True, "saved_count": len(validated_corrections), "path": legacy_path}


# OLD CORRECTIONS BACK-COMPAT ALIASES - REPLACED BY corrections_api.py
# @router.post("/review/{result_id}/corrections")
# async def save_corrections_compat(result_id: str, request: Request, body: Any = Body(None)):
#     """Alias for saving corrections under /review prefix (backwards compatibility)."""
#     return await post_corrections(result_id, request, body)


# OLD CORRECTIONS GET ENDPOINT - REPLACED BY corrections_api.py
# @router.get("/results/{result_id}/corrections")
# async def get_corrections(result_id: str):
#     base_id = normalize_result_id(result_id)
#     p = RESULTS_DIR / base_id / "corrections.json"
#     if not p.exists():
#         return {"items": [], "schema_version": 1}
#     try:
#         return json.loads(p.read_text("utf-8"))
#     except Exception:
#         return {"items": [], "schema_version": 1}


# OLD CORRECTIONS GET ALIAS - REPLACED BY corrections_api.py
# @router.get("/review/{result_id}/corrections")
# async def get_corrections_alias(result_id: str):
#     """Alias of /results/{result_id}/corrections for UI compatibility."""
#     return await get_corrections(result_id)


@router.post("/review/{result_id}/training")
async def add_review_training(result_id: str, payload: Dict[str, Any]):
    """Accept training data under review path; normalize result id before persisting."""
    base_id = normalize_result_id(result_id)
    training_dir = Path("/data/training") / base_id
    training_dir.mkdir(parents=True, exist_ok=True)
    training_file = training_dir / "training.json"
    data = {
        "result_id": base_id,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **payload,
    }
    training_file.write_text(json.dumps(data, indent=2))
    return {"ok": True, "path": str(training_file)}


@router.get("/results/{job_id}/extracted-text")
async def get_extracted_text(job_id: str):
    """Get extracted text for a job (moved from fileApi for consistency)"""
    # Normalize to ensure consistent IO regardless of incoming suffixes
    base_id = normalize_result_id(job_id)
    # Look for extracted text file in the outbox or a debug file
    text_file = OUTBOX / f"{base_id}.01_lines.debug.json"
    if not text_file.exists():
        # Try alternative locations
        alt_file = Path("/data") / "outbox" / f"{base_id}.01_lines.debug.json"
        if alt_file.exists():
            text_file = alt_file
        else:
            raise HTTPException(status_code=404, detail="Extracted text not found")
    
    try:
        data = json.loads(text_file.read_text(encoding="utf-8"))
        # Transform to expected format
        pages = []
        current_page = 1
        current_lines = []
        
        for line_data in data.get("lines", []):
            line_page = line_data.get("page", current_page)
            if line_page != current_page and current_lines:
                pages.append({"page": current_page, "lines": current_lines})
                current_lines = []
                current_page = line_page
            
            current_lines.append({
                "text": line_data.get("text", ""),
                "bbox": line_data.get("bbox", [0, 0, 0, 0]),
                "confidence": line_data.get("confidence", 1.0),
                "role": line_data.get("role")
            })
        
        # Add last page
        if current_lines:
            pages.append({"page": current_page, "lines": current_lines})
        
        return {"pages": pages}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read extracted text: {e}")


@router.get("/files/{result_id}/extracted-text")
async def get_files_extracted_text_compat(result_id: str):
    """Compatibility shim: proxies to /results/{base_id}/extracted-text."""
    rid = normalize_result_id(result_id)
    if rid != result_id:
        logger.warning("Incoming result id normalized: '%s' -> '%s'", result_id, rid)
    logger.debug("get_files_extracted_text_compat: incoming result_id='%s', normalized rid='%s'", result_id, rid)
    
    try:
        # First try the new canonical function
        logger.debug("Trying new canonical path for rid='%s'", rid)
        result = await get_extracted_text(rid)
        logger.debug("Success: new canonical path satisfied request for rid='%s'", rid)
        return result
    except HTTPException as e:
        if e.status_code == 404:
            logger.debug("New canonical path failed for rid='%s', trying fallback", rid)
            try:
                # Fallback: try with the original result_id (legacy path)
                result = await get_extracted_text(result_id)
                logger.debug("Success: fallback path satisfied request for result_id='%s'", result_id)
                return result
            except HTTPException:
                logger.debug("Both new and fallback paths failed for result_id='%s'", result_id)
                raise HTTPException(status_code=404, detail="Extracted text not found")
        else:
            # Re-raise non-404 errors
            raise


@router.get("/debug/routes")
async def list_routes_debug():
    """Debug endpoint to list all mounted routes"""
    return {"ok": True, "hint": "This is a placeholder - actual routes are shown at startup"}
