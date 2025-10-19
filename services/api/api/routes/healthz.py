# services/api/api/routes/healthz.py
from fastapi import APIRouter
try:
    # Counters/metrics from corrections API
    from api.corrections_api import invalid_shape_count_last  # type: ignore
except Exception:  # pragma: no cover
    invalid_shape_count_last = None  # type: ignore
try:
    # Import lazily to keep health endpoints light if module not present
    from services.corrections import get_apply_events  # type: ignore
except Exception:  # pragma: no cover
    get_apply_events = None

router = APIRouter()

@router.get("/ping")
def ping():
    return {"ok": True}

@router.get("/live")
def live():
    return {"status": "live"}

@router.get("/ready")
def ready():
    return {"status": "ready"}


@router.get("/details")
def details(limit: int = 20, invalid_window_minutes: int = 15):
    """Diagnostics: last N correction apply counts (no PHI)."""
    events = []
    if get_apply_events is not None:
        try:
            events = get_apply_events(limit=limit)  # type: ignore[misc]
        except Exception:
            events = []
    invalid_shape = None
    if invalid_shape_count_last is not None:
        try:
            invalid_shape = {
                "window": invalid_window_minutes,
                "count": invalid_shape_count_last(invalid_window_minutes)  # type: ignore[misc]
            }
        except Exception:
            invalid_shape = None
    return {
        "ok": True,
        "corrections_apply_events": events,
        "corrections_invalid_shape_last_minutes": invalid_shape,
    }
