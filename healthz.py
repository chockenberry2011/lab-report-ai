# /app/healthz.py
from fastapi import APIRouter

router = APIRouter()
r = router  # some code might use .r

@router.get("/ping")
def ping():
    return {"ok": True}

# Optional model status surface
_import_err = None
try:
    from services.worker import tasks
except Exception as e:
    tasks = None
    _import_err = repr(e)

@router.get("/models")
def models():
    if not tasks:
        return {
            "roles_model_exists": False,
            "testrow_model_exists": False,
            "roles_model_ok": False,
            "testrow_model_ok": False,
            "roles_used_fallback_last": None,
            "testrow_used_fallback_last": None,
            "import_error": _import_err,
        }
    
    # Check if models exist (including placeholders)
    roles_bundle = getattr(tasks, "_roles", None)
    testrow_bundle = getattr(tasks, "_testrow", None)
    
    return {
        "roles_model_exists": bool(roles_bundle and roles_bundle.ok),
        "testrow_model_exists": bool(testrow_bundle and testrow_bundle.ok),
        "roles_is_placeholder": bool(roles_bundle and roles_bundle.is_placeholder),
        "testrow_is_placeholder": bool(testrow_bundle and testrow_bundle.is_placeholder),
        "roles_model_ok": bool(getattr(tasks, "_roles_model_ok", False)),
        "testrow_model_ok": bool(getattr(tasks, "_testrow_model_ok", False)),
        "roles_used_fallback_last": getattr(tasks, "_roles_used_fallback_last", None),
        "testrow_used_fallback_last": getattr(tasks, "_testrow_used_fallback_last", None),
        "import_error": _import_err,
    }

@router.get("/env")
def env():
    import os
    keys = ["MODEL_ROLES_DIR","MODEL_TESTROW_DIR","REDIS_URL"]
    return {k: os.getenv(k) for k in keys}

@router.get("/paths")
def paths():
    import sys
    return {"sys_path": sys.path[:5]}