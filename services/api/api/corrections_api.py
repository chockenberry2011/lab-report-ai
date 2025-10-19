# corrections_api.py
from fastapi import APIRouter, Path, Response, HTTPException, Header, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Any, List, Optional, Dict, Union
from pathlib import Path as FSPath
import json, os, datetime, logging
from collections import deque
from datetime import datetime as dt, timedelta, timezone
from api.corrections.schema import FIELD_MAP, resolve_field, REQUIRED_FIELDS
from .services.results_io import (
    _canonical_path,
    _bootstrap_canonical,
    _load_corrections_list,
    _apply_correction,
)

log = logging.getLogger("api.corrections")
router = APIRouter()

DATA_ROOT = FSPath(os.environ.get("DATA_ROOT", "/data"))
RESULTS_DIR = DATA_ROOT / "results"

def normalize_id(result_id: str) -> str:
    return result_id.split(".", 1)[0]

# Lightweight counters and recent invalid-shape tracker (in-memory)
COUNTERS: Dict[str, int] = {
    "corrections.save.attempted": 0,
    "corrections.save.succeeded": 0,
    "corrections.save.failed_wrong_type": 0,
}

_INVALID_SHAPE_EVENTS = deque(maxlen=5000)  # type: ignore[var-annotated]

def _now():
    return dt.now(timezone.utc)

def record_invalid_shape(path: str, found: str, rid: str):
    _INVALID_SHAPE_EVENTS.append(_now())
    log.warning(
        "corrections_load_wrong_type expected=array found=%s",
        found,
        extra={"rid": rid, "path": path},
    )

def invalid_shape_count_last(minutes: int = 15) -> int:
    cutoff = _now() - timedelta(minutes=minutes)
    return sum(1 for t in _INVALID_SHAPE_EVENTS if t >= cutoff)

class Correction(BaseModel):
    field: Optional[str] = Field(None, description="Field name being corrected")
    old_value: Optional[Any] = Field(None, description="Original value")
    new_value: Optional[Any] = Field(None, description="Corrected value")
    note: Optional[str] = Field(None, description="Note about the correction")
    source: Optional[str] = Field(None, description="Source of the correction")
    location: Optional[Dict[str, Any]] = Field(None, description="Location metadata")
    # richer format support (optional)
    op: Optional[str] = Field("replace", description="Operation type")
    path: Optional[str] = Field(None, description="JSONPointer-like path")
    value: Optional[Any] = Field(None, description="Value for operation")
    ts: Optional[str] = Field(None, description="Timestamp")

class CorrectionsPayload(BaseModel):
    corrections: List[Dict[str, Any]] = Field(..., description="Array of correction objects")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error code")
    expected: str = Field(..., description="Expected type")
    found: str = Field(..., description="Found type")

class CorrectionsResponse(BaseModel):
    corrections: List[Dict[str, Any]] = Field(..., description="Array of all corrections after append")

def _coerce_to_array(payload: Any) -> List[Dict[str, Any]]:
    """
    Coerce incoming payload to a list of correction objects.

    Accepts:
    - List of objects (pass through)
    - Single object (wrap in array)
    - Dict with "corrections" key containing list
    """
    if isinstance(payload, list):
        log.info("incoming_payload_is_array", extra={"count": len(payload)})
        return payload
    elif isinstance(payload, dict):
        if "corrections" in payload and isinstance(payload["corrections"], list):
            log.info("incoming_payload_is_wrapper", extra={"count": len(payload["corrections"])})
            return payload["corrections"]
        else:
            # Single object - coerce to array
            log.info("incoming_coerced_to_array", extra={"original_type": "dict"})
            return [payload]
    else:
        raise HTTPException(status_code=400, detail="Invalid payload format")

def _normalize_corrections(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize correction objects and enforce field schema.

    - Ensure op default
    - Prefer 'new_value' over 'value' for replacement, final key is 'value'
    - Resolve 'field' aliases to canonical keys when present (no 'path')
    - Enforce required fields non-empty
    """
    now = datetime.datetime.utcnow().isoformat() + "Z"
    normalized: List[Dict[str, Any]] = []
    valid_keys = list(FIELD_MAP.keys())
    for raw in items:
        c = dict(raw)
        c.setdefault("op", "replace")
        # Prefer new_value for replacement
        replacement = c.get("new_value") if c.get("new_value") is not None else c.get("value")
        if replacement is not None:
            c["value"] = replacement
        c.setdefault("ts", now)

        # Field-key normalization only when 'field' is provided and no explicit 'path'
        if c.get("field") and not c.get("path"):
            incoming = str(c.get("field"))
            canon = resolve_field(incoming)
            if not canon:
                log.warning("unknown_field_key incoming=%s valid=%s", incoming, valid_keys)
                # Skip unknown field entries
                continue
            # Enforce: required fields must not be empty on replace
            if canon in REQUIRED_FIELDS:
                val = c.get("value")
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    raise HTTPException(status_code=400, detail={"error": "value_required", "field": incoming})
            c["field"] = canon

        normalized.append(c)
    return normalized

def _corrections_path(result_id: str) -> FSPath:
    rid = normalize_id(result_id)
    return RESULTS_DIR / rid / "corrections.json"

@router.post("/results/{result_id}/corrections", tags=["corrections"])
async def save_corrections(request: Request, result_id: str = Path(...)):
    """Hardened corrections ingestion with correlation id and compose."""
    rid = normalize_id(result_id)
    req_id = getattr(request.state, 'req_id', None)
    path = _corrections_path(result_id)
    COUNTERS["corrections.save.attempted"] += 1

    # Log request context
    ctype = request.headers.get("content-type", "")
    raw = await request.body()
    log.info("incoming_corrections ctype=%s bytes=%d", ctype, len(raw), extra={"rid": rid, "req_id": req_id})
    if not ctype.startswith("application/json"):
        body = {"error": "bad_content_type", "detail": "expected application/json", "req_id": req_id}
        log.warning("bad_content_type %s", body, extra={"rid": rid, "req_id": req_id})
        return JSONResponse(status_code=400, content=body)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        body = {"error": "invalid_json", "req_id": req_id}
        log.warning("invalid_json %s", body, extra={"rid": rid, "req_id": req_id})
        return JSONResponse(status_code=400, content=body)
    if not isinstance(payload, list):
        body = {"error": "payload_must_be_array", "req_id": req_id}
        log.warning("payload_must_be_array %s", body, extra={"rid": rid, "req_id": req_id})
        return JSONResponse(status_code=400, content=body)

    # Log first item preview
    if payload:
        first = dict(payload[0]) if isinstance(payload[0], dict) else {"_": "non-object"}
        preview = {"field": first.get("field"), "op": first.get("op"), "has_value": bool(first.get("value") or first.get("new_value")), "ts": first.get("ts")}
        log.info("payload_preview %s", preview, extra={"rid": rid, "req_id": req_id})

    # Normalize and validate
    normalized_incoming = _normalize_corrections(payload)
    valid_keys = sorted(list(FIELD_MAP.keys()))[:20]
    for it in normalized_incoming:
        if it.get("path"):
            continue
        f = it.get("field")
        if not f or f not in FIELD_MAP:
            body = {"error": "unknown_field", "field": it.get("field"), "accepted": valid_keys, "req_id": req_id}
            log.warning("unknown_field %s", body, extra={"rid": rid, "req_id": req_id})
            return JSONResponse(status_code=400, content=body)
        if f in REQUIRED_FIELDS:
            v = it.get("value")
            if v is None or (isinstance(v, str) and v.strip() == ""):
                body = {"error": "value_required", "field": f, "req_id": req_id}
                log.warning("value_required %s", body, extra={"rid": rid, "req_id": req_id})
                return JSONResponse(status_code=400, content=body)

    # Load existing corrections with strict validation
    existing_corrections: List[Dict[str, Any]] = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
            detected_type = type(existing_data).__name__
            log.info("load_existing_corrections type=%s", detected_type, extra={"rid": rid, "path": str(path), "req_id": req_id})
            if isinstance(existing_data, list):
                existing_corrections = existing_data
            else:
                found_type = detected_type
                log.error("load_wrong_type expected=array found=%s", found_type, extra={"rid": rid, "path": str(path), "req_id": req_id})
                COUNTERS["corrections.save.failed_wrong_type"] += 1
                record_invalid_shape(str(path), found_type, rid)
                return JSONResponse(status_code=422, content={"error": "CORRECTIONS_FILE_WRONG_TYPE", "expected": "array", "found": found_type, "req_id": req_id})
        except Exception:
            log.exception("Failed loading existing corrections", extra={"rid": rid, "path": str(path), "req_id": req_id})
            raise HTTPException(status_code=500, detail="Failed to load existing corrections")
    else:
        # Bootstrap empty list file atomically
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp0 = path.with_suffix(path.suffix + ".tmp0")
            with tmp0.open("w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False)
                f.flush()
                import os
                os.fsync(f.fileno())
            tmp0.replace(path)
            log.info("corrections_bootstrap creating file", extra={"rid": rid, "path": str(path), "req_id": req_id})
        except Exception:
            log.exception("bootstrap_write_failed", extra={"rid": rid, "path": str(path), "req_id": req_id})
            raise HTTPException(status_code=500, detail="Failed to initialize corrections file")
        log.info("load_ok", extra={"rid": rid, "path": str(path), "count": 0, "new_file": True, "req_id": req_id})

    all_corrections = existing_corrections + normalized_incoming

    # Persist atomically
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(all_corrections, f, ensure_ascii=False, indent=2)
            f.flush()
            import os
            os.fsync(f.fileno())
        tmp.replace(path)
        log.info("append_ok", extra={"rid": rid, "path": str(path), "existing_count": len(existing_corrections), "new_count": len(normalized_incoming), "total_count": len(all_corrections), "req_id": req_id})
        COUNTERS["corrections.save.succeeded"] += 1
        # Compose/merge
        applied = 0
        try:
            doc = _bootstrap_canonical(rid)
            for c in sorted(all_corrections, key=lambda x: x.get("ts") or ""):
                if _apply_correction(rid, c):
                    applied += 1
            cpath = _canonical_path(rid)
            cpath.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            log.info("compose_merge applied=%d target=%s", applied, str(cpath), extra={"rid": rid, "req_id": req_id})
        except Exception:
            applied = 0
        first_canonical = None
        if normalized_incoming:
            first_canonical = normalized_incoming[0].get("field") or normalized_incoming[0].get("path")
        # Emit apply_ok summary with has_value and total length
        try:
            log.info(
                "apply_ok",
                extra={
                    "rid": rid,
                    "field": first_canonical,
                    "has_value": bool((normalized_incoming[0] or {}).get("value")),
                    "len_total": len(all_corrections),
                    "req_id": req_id,
                },
            )
        except Exception:
            pass
        return JSONResponse(status_code=200, content={"ok": True, "applied": applied, "canonical_field": first_canonical, "req_id": req_id})
    except Exception as e:
        log.error("persist_error", extra={"rid": rid, "path": str(path), "error": str(e), "req_id": req_id})
        raise HTTPException(status_code=500, detail="Failed to persist corrections")

@router.get("/results/{result_id}/corrections", tags=["corrections"])
async def get_corrections(
    result_id: str = Path(...)
):
    rid = normalize_id(result_id)
    path = _corrections_path(result_id)
    if not path.exists():
        log.info("No corrections file yet", extra={"rid": rid, "path": str(path)})
        return JSONResponse(
            content={"corrections": []},
            headers={"Cache-Control": "no-store"}
        )
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        dtype = type(data).__name__
        log.info("get_corrections_load type=%s", dtype, extra={"rid": rid, "path": str(path)})
        # normalize on the way out
        if isinstance(data, list):
            data = {"corrections": data}
        elif isinstance(data, dict) and "corrections" in data and isinstance(data["corrections"], list):
            pass
        else:
            # tolerate weird legacy shapes by wrapping, but count/log it
            record_invalid_shape(str(path), dtype, rid)
            data = {"corrections": [data]}
        log.info(
            "get_corrections_return",
            extra={"rid": rid, "path": str(path), "count": len(data.get("corrections", []))},
        )
        return JSONResponse(
            content=data,
            headers={"Cache-Control": "no-store"}
        )
    except Exception as e:
        log.exception("get_corrections_exception", extra={"rid": rid, "path": str(path)})
        raise HTTPException(status_code=500, detail="Failed to load corrections")

@router.get("/schema/fields", tags=["corrections"])
async def get_corrections_field_schema():
    """Expose canonical field keys and their aliases for UI introspection."""
    schema = {
        key: {
            "aliases": FIELD_MAP.get(key, []),
            "required": key in REQUIRED_FIELDS,
        }
        for key in FIELD_MAP.keys()
    }
    return {"fields": schema}

@router.get("/healthz/details", tags=["health"])
async def details(limit: int = 20):
    # include last save path for easy debugging (no PHI)
    return {"ok": True, "data_root": str(DATA_ROOT)}
