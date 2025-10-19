"""
Lab AI Worker Tasks - Complete processing pipeline

Pipeline: PDF → Extractor → Roles → Headers/Specimen/Patient → TestRow → Composer → Confidence → JSON
"""

import os
import json
import time
import tempfile
import traceback
import requests
import inspect
import logging
import re
import sys
import joblib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import redis
from celery import Celery
from celery.utils.log import get_task_logger
from celery.signals import task_prerun
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTTextLine, LTTextLineHorizontal, LTChar, LAParams

# Import processing modules
from services.extractor.pdf_extractor import PDFExtractor
from services.worker.runtime.roles_infer import predict_line_roles, Line, RoleProb
# Note: Do not import runtime.testrow_infer here; we use local CRF artifacts
from services.worker.composer.composer import PanelComposer
from services.worker.model_io import load_roles_model
from services.worker.models.testrow_loader import TestRowModelAdapter, load_testrow_adapter
from services.worker.testrow.pipeline import build_testrow_pipeline
from services.worker.fallbacks import tag_panels_rule_first, tag_testrows_rule_first, apply_header_footer_quarantine
# NEW: EHR-compatible schema for structured output
from services.worker.schema import DiagnosticReport, Vendor, Patient, Specimen, OrderingProvider, Panel, TestRow, ReferenceRange, TestCode, Address, ReportInfo, PerformingLab, OrderingLocation, ReportMeta
# NEW: Meta extraction functions for structured data
from services.worker.extractors.meta_extractors import extract_vendor, extract_patient, extract_ordering, extract_specimen, extract_report_meta
# NEW: Normalization helpers for enhanced test row extraction
from services.worker.extractors.normalize import normalize_date, normalize_phone

# Additional imports for CRF functionality
import re
import json
import logging
from pathlib import Path
import joblib

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CELERY_BROKER = os.getenv("CELERY_BROKER", REDIS_URL)
CELERY_BACKEND = os.getenv("CELERY_BACKEND", REDIS_URL)
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
OUTBOX_DIR = DATA_DIR / "outbox"
INBOX_DIR = DATA_DIR / "inbox"
TEMP_DIR = DATA_DIR / "temp"

# Lab processing configuration
LAB_DEBUG = os.getenv("LAB_DEBUG", "0") == "1"
LAB_FORCE_FALLBACK = os.getenv("LAB_FORCE_FALLBACK", "0") == "1"
MODELS_DIR = Path("/models")
ROLES_MODEL_DIR = MODELS_DIR / "roles"
TESTROW_MODEL_DIR = MODELS_DIR / "testrow"

# Environment feature flags (read once at import)
FALLBACK_RULES_STRICT = int(os.getenv("FALLBACK_RULES_STRICT", "1"))
MODEL_MIN_CONF = float(os.getenv("MODEL_MIN_CONF", "0.60"))
LAB_DEBUG_DUMPS = int(os.getenv("LAB_DEBUG_DUMPS", "1"))
LAB_DEBUG_DIR = Path(os.getenv("LAB_DEBUG_DIR", "/data/outbox"))

# Composition feature flags with environment overrides
COMPOSITION_FLAGS = {
    "extract_meta": os.getenv("LABAI_EXTRACT_META", "1") != "0",
    "panel_code_detection": os.getenv("LABAI_PANEL_CODE_DETECTION", "1") != "0",
    "panel_comment_detection": os.getenv("LABAI_PANEL_COMMENT_DETECTION", "1") != "0",
    "test_extras_detection": os.getenv("LABAI_TEST_EXTRAS_DETECTION", "1") != "0"
}

# Model loading at module import with guarded fallbacks
def _load_models_with_logging():
    """Load models with proper error handling and logging"""
    global _roles, _testrow, _roles_model_ok, _testrow_model_ok
    
    # Get logger (will be available after Celery setup)
    try:
        from celery.utils.log import get_task_logger
        log = get_task_logger(__name__)
    except:
        import logging
        log = logging.getLogger(__name__)
    
    # Try to load roles model
    try:
        _roles = load_roles_model()
        _roles_model_ok = _roles.ok
        if _roles_model_ok:
            if _roles.is_placeholder:
                log.info(f"roles model: PLACEHOLDER at {_roles.path} → using rules")
                _roles_model_ok = False  # Treat placeholder as not available for ML
            else:
                # Read metadata to determine embedding model type
                embedding_model = _roles.meta.get('embedding_model', 'sbert')
                
                if embedding_model == "tfidf":
                    # TF-IDF model - load joblib + metadata, NO sentence_transformers import
                    import joblib
                    import os
                    model_path = os.path.join(_roles.path, "model.joblib")
                    if os.path.exists(model_path):
                        try:
                            # Load and verify the model
                            joblib.load(model_path)
                            log.info("roles: loaded tfidf model")
                            _roles_model_ok = True
                        except Exception as e:
                            log.warning(f"roles: failed to load tfidf model: {e}")
                            _roles_model_ok = False
                    else:
                        log.warning(f"roles: tfidf model.joblib not found at {_roles.path}")
                        _roles_model_ok = False
                else:
                    # SBERT branch - keep for non-tfidf models only
                    log.info(f"roles model: LOADED from {_roles.path} (embedding: {embedding_model})") 
                    _roles_model_ok = True
        else:
            log.info("roles model: MISSING → using rules")
    except Exception as e:
        _roles = None
        _roles_model_ok = False
        log.warning(f"roles model: ERROR ({e}) → using rules")
    
    # Try to load testrow model (old PyTorch/HuggingFace model)
    try:
        from .model_io import load_testrow_model as load_testrow_pytorch_model
        _testrow = load_testrow_pytorch_model()
        old_testrow_model_ok = _testrow.ok
        if old_testrow_model_ok:
            if _testrow.is_placeholder:
                log.info(f"testrow PyTorch model: PLACEHOLDER at {_testrow.path} → using rules")
                old_testrow_model_ok = False  # Treat placeholder as not available for ML
            else:
                log.info(f"testrow PyTorch model: LOADED from {_testrow.path}")
        else:
            log.info("testrow PyTorch model: MISSING → using rules")
    except Exception as e:
        _testrow = None
        old_testrow_model_ok = False
        log.warning(f"testrow PyTorch model: ERROR ({e}) → using rules")

    # Load the TestRow model via adapter at startup
    try:
        load_testrow_model()
        if globals().get("_testrow_model_ok"):
            labels_count = len(globals().get("_testrow_labels", []))
            log.info(f"testrow model: LOADED with {labels_count} labels (adapter)")
        else:
            log.info("testrow model: MISSING → using fallback")
    except Exception as e:
        log.warning(f"testrow model: ERROR ({e}) → using fallback")
        globals()["_testrow_model_ok"] = False

# Initialize model state
_roles = None
_testrow = None
_roles_model_ok = False
_roles_used_fallback_last = None
_roles_fallback_reason_last = None

# test-row model globals (adapter-based)
_testrow_model_ok = False
_testrow_used_fallback_last = None
_testrow_crf = None          # legacy; not used with adapter
_testrow_model: Optional[TestRowModelAdapter] = None
_testrow_labels: List[str] = []

# Module-level singleton pipeline for test-row parsing (initialized at import)
_testrow_pipeline = build_testrow_pipeline()
if _testrow_pipeline is not None:
    _testrow_model_ok = True

# CRF loading helper
def _load_crf_from_dir(dir_path: str):
    """
    Return a CRF-like object with .predict() and .predict_marginals_single() if available.
    Try, in order:
      1) models.testrow.loader.load(dir_path)
      2) joblib.load(<dir>/crf.joblib)
      3) joblib.load(<dir>/model.crf)
    Raise the original exception if all fail.
    """
    import importlib.util, pathlib, joblib, sys

    d = pathlib.Path(dir_path)

    # (1) Try optional loader.py
    loader_py = d / "loader.py"
    if loader_py.exists():
        spec = importlib.util.spec_from_file_location("models.testrow.loader", str(loader_py))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["models.testrow.loader"] = mod
        spec.loader.exec_module(mod)  # type: ignore
        if hasattr(mod, "load"):
            return mod.load(str(d))

    # (2) Try crf.joblib
    p = d / "crf.joblib"
    if p.exists():
        return joblib.load(p)

    # (3) Try model.crf
    p = d / "model.crf"
    if p.exists():
        return joblib.load(p)

    raise FileNotFoundError(f"No supported model artifact in {dir_path} (need crf.joblib or model.crf).")

# CRF helper functions (module scope)
def _crf_sent_from_text(text: str):
    tokens = []
    for m in re.finditer(r'\S+', text or ""):
        tokens.append({"token": m.group(0), "start_pos": m.start(), "end_pos": m.end()})
    return tokens

def _crf_word2features(sent, i):
    w = sent[i]["token"]
    feats = {
        "bias": 1.0,
        "w.lower": w.lower(),
        "w.isdigit": w.isdigit(),
        "w.isupper": w.isupper(),
        "w.istitle": w.istitle(),
        "sfx3": w[-3:],
        "has%": "%" in w,
        "has/": "/" in w,
        "has-": "-" in w or "–" in w or "—" in w,
        "has(": "(" in w,
        "has)": ")" in w,
    }
    if i > 0:
        p = sent[i-1]["token"]
        feats.update({"-1.w.lower": p.lower(), "-1.w.istitle": p.istitle(), "-1.w.isupper": p.isupper()})
    else:
        feats["BOS"] = True
    if i < len(sent)-1:
        n = sent[i+1]["token"]
        feats.update({"+1.w.lower": n.lower(), "+1.w.istitle": n.istitle(), "+1.w.isupper": n.isupper()})
    else:
        feats["EOS"] = True
    return feats

# Ensure directories exist
for directory in [OUTBOX_DIR, INBOX_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Debug dumper function
def write_debug_file(job_id: str, stage: str, data: Any):
    """Write debug file if LAB_DEBUG_DUMPS is enabled"""
    if not LAB_DEBUG_DUMPS:
        return
    
    try:
        LAB_DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        debug_path = LAB_DEBUG_DIR / f"{job_id}.{stage}.debug.json"
        with open(debug_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        logger.debug(f"Debug file written: {debug_path}")
    except Exception as e:
        logger.warning(f"Failed to write debug file for {stage}: {e}")

def truncate_for_debug(text: str, max_length: int = 500) -> str:
    """Safely truncate text for debug dumps"""
    if not text or not isinstance(text, str):
        return text
    if len(text) <= max_length:
        return text
    return text[:max_length] + "... [TRUNCATED]"

def _coerce_ref_range(rr):
    """
    Accepts either:
      - str: e.g. "70-99" or "70-99 01", returns {'text': str, 'low': float|None, 'high': float|None}
      - dict: may include keys like 'text'/'raw' and optionally 'low'/'high' (or 'min'/'max')
      - None/other: returns dict with text and None low/high
    """
    if rr is None:
        return {"text": None, "low": None, "high": None}
    if isinstance(rr, str):
        text = rr.strip() or None
        low = high = None
        # Try best-effort numeric range parse:  70-99  |  -1.2 – 3.4
        m = re.search(r'(-?\d+(?:\.\d+)?)\s*[-–]\s*(-?\d+(?:\.\d+)?)', rr)
        if m:
            try:
                low = float(m.group(1))
                high = float(m.group(2))
            except Exception:
                low = high = None
        return {"text": text, "low": low, "high": high}

    if isinstance(rr, dict):
        text = rr.get("text") or rr.get("raw") or rr.get("value") or None
        low  = rr.get("low", rr.get("min"))
        high = rr.get("high", rr.get("max"))
        # Try to coerce numeric if they're strings
        def _num(x):
            try:
                return float(x) if x is not None and str(x).strip() != "" else None
            except Exception:
                return None
        return {"text": text, "low": _num(low), "high": _num(high)}

    # Fallback
    return {"text": str(rr), "low": None, "high": None}

def _coerce_flag(flag):
    """
    Normalize flag to a short string like 'H','L','CRIT', or None.
    Input may be None, str, or list[str].
    """
    if not flag:
        return None
    if isinstance(flag, list):
        return (flag[0] if flag else None) or None
    return (str(flag).strip() or None)

def enhance_debug_data(stage: str, original_data: Any, header_result: Any = None, composition_result: Any = None) -> Any:
    """
    Enhance debug data with metadata while keeping sizes reasonable.
    
    Enhancement features are controlled by COMPOSITION_FLAGS:
    - extract_meta: Controls metadata extraction (vendor, patient, specimen, ordering, report_meta)
    - panel_code_detection: Controls panel code enhancement in debug output
    - panel_comment_detection: Controls panel comment enhancement in debug output  
    - test_extras_detection: Controls test row extras (codes, methodology, comments, observed_at)
    
    Args:
        stage: Debug stage identifier ('02_roles', '03_compose', etc.)
        original_data: Original data to enhance
        header_result: Optional header extraction results for metadata enhancement
        composition_result: Optional composition results for panel/test enhancement
        
    Returns:
        Enhanced data with additional debug information based on enabled flags
    """
    # NEW: Add metadata to debug dumps
    try:
        import copy
        enhanced_data = copy.deepcopy(original_data)
        
        if stage == "02_roles" and header_result:
            # Add metadata extraction results to roles debug
            enhanced_data["meta_extraction"] = {}
            
            # Add vendor info (truncated) - controlled by extract_meta flag
            if COMPOSITION_FLAGS["extract_meta"] and header_result.get("vendor_info"):
                vendor = header_result["vendor_info"].copy()
                if vendor.get("name"):
                    vendor["name"] = truncate_for_debug(vendor["name"], 100)
                if vendor.get("address") and isinstance(vendor["address"], dict):
                    # Truncate address fields
                    for addr_key in ["street", "city"]:
                        if vendor["address"].get(addr_key):
                            vendor["address"][addr_key] = truncate_for_debug(vendor["address"][addr_key], 100)
                enhanced_data["meta_extraction"]["vendor"] = vendor
            
            # Add patient info (truncated) - controlled by extract_meta flag
            if COMPOSITION_FLAGS["extract_meta"] and header_result.get("patient_info_structured"):
                patient = header_result["patient_info_structured"].copy()
                for field in ["first_name", "last_name", "middle"]:
                    if patient.get(field):
                        patient[field] = truncate_for_debug(patient[field], 50)
                if patient.get("address") and isinstance(patient["address"], dict):
                    for addr_key in ["street", "city"]:
                        if patient["address"].get(addr_key):
                            patient["address"][addr_key] = truncate_for_debug(patient["address"][addr_key], 100)
                enhanced_data["meta_extraction"]["patient"] = patient
            
            # Add specimen info - controlled by extract_meta flag
            if COMPOSITION_FLAGS["extract_meta"] and header_result.get("specimen_info_structured"):
                specimen = header_result["specimen_info_structured"].copy()
                if specimen.get("type"):
                    specimen["type"] = truncate_for_debug(specimen["type"], 100)
                enhanced_data["meta_extraction"]["specimen"] = specimen
            
            # Add ordering info (truncated) - controlled by extract_meta flag
            if COMPOSITION_FLAGS["extract_meta"] and header_result.get("ordering_info"):
                ordering = header_result["ordering_info"].copy()
                if ordering.get("provider_name"):
                    ordering["provider_name"] = truncate_for_debug(ordering["provider_name"], 100)
                if ordering.get("location") and isinstance(ordering["location"], dict):
                    if ordering["location"].get("name"):
                        ordering["location"]["name"] = truncate_for_debug(ordering["location"]["name"], 100)
                enhanced_data["meta_extraction"]["ordering"] = ordering
            
            # Add report meta (truncated) - controlled by extract_meta flag
            if COMPOSITION_FLAGS["extract_meta"] and header_result.get("report_meta_info"):
                report_meta = header_result["report_meta_info"].copy()
                if report_meta.get("clinical_info"):
                    report_meta["clinical_info"] = truncate_for_debug(report_meta["clinical_info"])
                if report_meta.get("comments"):
                    report_meta["comments"] = truncate_for_debug(report_meta["comments"])
                if report_meta.get("ordered_items") and isinstance(report_meta["ordered_items"], list):
                    # Truncate each item and limit list size
                    report_meta["ordered_items"] = [
                        truncate_for_debug(item, 100) for item in report_meta["ordered_items"][:10]
                    ]
                enhanced_data["meta_extraction"]["report_meta"] = report_meta
        
        elif stage == "03_compose" and composition_result:
            # Enhance composition result with panel and test extras
            if enhanced_data.get("lab_panels"):
                for panel in enhanced_data["lab_panels"]:
                    # Add panel enhancements
                    panel_extras = {}
                    
                    # Add panel code if present - controlled by panel_code_detection flag
                    if COMPOSITION_FLAGS["panel_code_detection"] and panel.get("panel_code"):
                        panel_extras["code"] = truncate_for_debug(panel["panel_code"], 100)
                    
                    # Add panel comments if present (truncated) - controlled by panel_comment_detection flag
                    if COMPOSITION_FLAGS["panel_comment_detection"] and panel.get("comments"):
                        panel_extras["comments"] = truncate_for_debug(panel["comments"])
                    
                    if panel_extras:
                        panel["debug_extras"] = panel_extras
                    
                    # Add test row enhancements - controlled by test_extras_detection flag
                    if COMPOSITION_FLAGS["test_extras_detection"] and panel.get("test_rows"):
                        for test_row in panel["test_rows"]:
                            test_extras = {}
                            
                            # Add codes if present
                            if test_row.get("codes"):
                                test_extras["codes"] = test_row["codes"]
                            
                            # Add methodology (truncated)
                            if test_row.get("methodology"):
                                test_extras["methodology"] = truncate_for_debug(test_row["methodology"], 200)
                            
                            # Add comments (truncated)
                            if test_row.get("comments"):
                                test_extras["comments"] = truncate_for_debug(test_row["comments"])
                            
                            # Add observation time
                            if test_row.get("observed_at"):
                                test_extras["observed_at"] = test_row["observed_at"]
                            
                            if test_extras:
                                test_row["debug_extras"] = test_extras
        
        return enhanced_data
        
    except Exception as e:
        logger.warning(f"Failed to enhance debug data for {stage}: {e}")
        return original_data

def assert_models_or_raise(stage: str):
    """Assert that required models are loaded for a stage, raise clear exception if missing"""
    missing_models = []
    
    if stage in ['roles', 'full'] and not _roles_model_ok:
        missing_models.append('roles')
    
    if stage in ['testrow', 'full'] and not _testrow_model_ok:
        missing_models.append('testrow')
    
    if missing_models:
        raise ProcessingError(
            f"Required models not loaded for stage '{stage}': {', '.join(missing_models)}. "
            f"Check model files and configuration."
        )

# Startup logging for model paths
def log_model_paths():
    """Log model directory status on startup"""
    logger.info("🔍 Lab AI Model Path Status:")
    
    for name, path in [("roles", ROLES_MODEL_DIR), ("testrow", TESTROW_MODEL_DIR)]:
        if path.exists():
            files = list(path.glob("*"))
            logger.info(f"  ✅ {name}: {path} ({len(files)} files)")
        else:
            logger.info(f"  ❌ {name}: {path} (not found)")
    
    if LAB_FORCE_FALLBACK:
        logger.info("  ⚠️  LAB_FORCE_FALLBACK=1 - Models will be skipped")
    
    if LAB_DEBUG:
        logger.info(f"  🐛 LAB_DEBUG=1 - Debug files will be written to {OUTBOX_DIR}")

# Celery app setup
app = Celery('lab_ai_worker', broker=CELERY_BROKER, backend=CELERY_BACKEND)
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'worker.process_lab_report': {'queue': 'lab_processing'},
    },
    worker_concurrency=1,  # Ensure concurrency = 1
    worker_prefetch_multiplier=1,  # Process one task at a time
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Additional settings for single-threaded processing
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    task_time_limit=1800,  # 30 minute hard limit per task
    task_soft_time_limit=1500,  # 25 minute soft limit
)

# Redis connection with retry logic
logger = get_task_logger(__name__)

# Load models with logging now that logger is available (no CRF load at import)
_load_models_with_logging()

def _log_model_details():
    """Log detailed model information at startup"""
    logger.info("🚀 Worker Model Status at Startup:")
    
    # Roles model details
    if _roles_model_ok and _roles:
        try:
            # Try to read metadata
            metadata_path = Path(_roles.path) / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                labels = metadata.get('labels', [])
                version = metadata.get('version', 'unknown')
                logger.info(f"  ✅ Roles model: {len(labels)} labels, version {version}")
                logger.info(f"     Labels: {', '.join(labels[:10])}{'...' if len(labels) > 10 else ''}")
            else:
                logger.info(f"  ✅ Roles model: loaded from {_roles.path} (no metadata.json)")
        except Exception as e:
            logger.info(f"  ✅ Roles model: loaded from {_roles.path} (metadata read error: {e})")
    else:
        logger.info(f"  ❌ Roles model: not available")
    
    # TestRow model details
    if globals().get('old_testrow_model_ok', False) and _testrow:
        logger.info(f"  ✅ TestRow PyTorch model: loaded from {_testrow.path}")
    else:
        logger.info(f"  ❌ TestRow PyTorch model: not available")
    
    # CRF model details  
    if globals().get('_testrow_model_ok', False):
        logger.info(f"  ✅ TestRow CRF model: loaded")
    else:
        logger.info(f"  ❌ TestRow CRF model: not available")

# Log model details after loading
_log_model_details()

def update_job_indices(r, jid: str, status: str, updated_at_iso: str):
    """Centralized function to update all job indices"""
    ts = datetime.fromisoformat(updated_at_iso).timestamp() if updated_at_iso else float(r.time()[0])

    pipe = r.pipeline(transaction=False)
    # ensure membership
    pipe.sadd("jobs:all", jid)
    # status sets (remove from others, add to current)
    for s in ("queued", "processing", "done", "failed"):
        if s == status:
            pipe.sadd(f"jobs:status:{s}", jid)
        else:
            pipe.srem(f"jobs:status:{s}", jid)
    # indices
    pipe.zadd("jobs:index", {jid: ts})
    pipe.zadd("jobs:recent", {jid: ts})
    pipe.zadd("jobs:by_updated_at", {jid: ts})
    pipe.execute()

def connect_to_redis_with_retry(redis_url: str, max_duration: int = 120) -> redis.Redis:
    """
    Connect to Redis with exponential backoff retry logic.
    
    Args:
        redis_url: Redis connection URL
        max_duration: Maximum time to retry in seconds (default: 2 minutes)
    
    Returns:
        Redis client instance
        
    Raises:
        ConnectionError: If unable to connect after max_duration
    """
    start_time = time.time()
    retry_delay = 0.5  # Start with 0.5 seconds
    max_delay = 30.0   # Cap at 30 seconds
    
    logger.info(f"Connecting to Redis at {redis_url}")
    
    while time.time() - start_time < max_duration:
        try:
            client = redis.from_url(redis_url, socket_timeout=5, socket_connect_timeout=5)
            # Test the connection
            client.ping()
            logger.info("✅ Redis connection established successfully")
            logger.info("🟢 Ready for jobs")
            return client
            
        except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
            elapsed = time.time() - start_time
            remaining = max_duration - elapsed
            
            if remaining <= 0:
                logger.error(f"❌ Failed to connect to Redis after {max_duration}s. Last error: {str(e)}")
                raise ConnectionError(f"Unable to connect to Redis after {max_duration} seconds: {str(e)}")
            
            logger.warning(f"⚠️  Redis connection failed (attempt after {elapsed:.1f}s): {str(e)}")
            logger.info(f"🔄 Retrying in {retry_delay:.1f}s (remaining time: {remaining:.1f}s)")
            
            time.sleep(retry_delay)
            
            # Exponential backoff: double the delay, but cap at max_delay
            retry_delay = min(retry_delay * 2, max_delay)
    
    # Final attempt that will raise the exception
    logger.error(f"❌ Redis connection timeout after {max_duration} seconds")
    raise ConnectionError(f"Unable to connect to Redis after {max_duration} seconds")

# Initialize Redis connection with retry
redis_client = connect_to_redis_with_retry(REDIS_URL)

def _score_from_hash(h: dict) -> float:
    """Extract timestamp score from job hash for sorting"""
    for k in ("updated_at", "started_at", "created_at", "completed_at"):
        v = h.get(k)
        if v:
            try:
                return datetime.fromisoformat(v).timestamp()
            except Exception:
                pass
    # fallback: "now" to keep order stable-ish
    return float(redis_client.time()[0])

def rebuild_indices_if_missing():
    """Rebuild job indices on worker startup if they're missing"""
    try:
        need = not (redis_client.exists("jobs:index") and redis_client.exists("jobs:recent") and redis_client.exists("jobs:by_updated_at"))
        if not need:
            return
        
        logger.info("🔄 Worker rebuilding missing job indices...")
        ids = redis_client.smembers("jobs:all") or set()
        pipe = redis_client.pipeline(transaction=False)
        
        # Clear existing indices
        for z in ("jobs:index", "jobs:recent", "jobs:by_updated_at"):
            pipe.delete(z)
        
        # Rebuild indices
        for jid in ids:
            h = redis_client.hgetall(f"job:{jid}") or {}
            s = _score_from_hash(h)
            pipe.zadd("jobs:index", {jid: s})
            pipe.zadd("jobs:recent", {jid: s})
            pipe.zadd("jobs:by_updated_at", {jid: s})
        
        pipe.execute()
        logger.info(f"✅ Worker rebuilt job indices for {len(ids)} jobs")
    except Exception as e:
        logger.warning(f"Failed to rebuild indices on worker startup: {str(e)}")

# Rebuild indices on worker startup
rebuild_indices_if_missing()

# Log model paths on worker startup
log_model_paths()

# Celery signal handler for task dequeue
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
    """Handle task dequeue - set status to processing"""
    if task and task.name == 'worker.process_lab_report' and args:
        job_id = args[0]  # First argument is job_id
        logger.info(f"📥 Job {job_id} dequeued - setting status to processing")
        
        try:
            # This will be called again in the task, but ensures immediate status update
            update_job_status(job_id, "processing")
        except Exception as e:
            logger.warning(f"Failed to update status on dequeue for job {job_id}: {str(e)}")

class ProcessingError(Exception):
    """Custom exception for processing errors"""
    pass

def log_progress(job_id: str, stage: str, message: str, progress: float = None, extra_data: dict = None):
    """Log progress to Redis for job tracking"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    log_entry = {
        "timestamp": timestamp,
        "stage": stage,
        "message": message,
        "progress": progress,
        **(extra_data or {})
    }
    
    # Update progress in job data
    current_progress = redis_client.hget(f"job:{job_id}", "progress")
    if current_progress:
        try:
            progress_data = json.loads(current_progress.decode('utf-8'))
        except:
            progress_data = {}
    else:
        progress_data = {}
    
    progress_data[stage] = {
        "message": message,
        "timestamp": timestamp,
        "progress": progress,
        **(extra_data or {})
    }
    
    # Store updated progress
    redis_client.hset(f"job:{job_id}", "progress", json.dumps(progress_data))
    
    # Add to logs
    redis_client.lpush(f"job:{job_id}:logs", json.dumps(log_entry))
    redis_client.expire(f"job:{job_id}:logs", 86400 * 7)  # Keep logs for 7 days
    
    logger.info(f"Job {job_id} - {stage}: {message}")

def update_job_status(job_id: str, status: str, **kwargs):
    """Update job status in both Redis and JobRegistry"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Prepare updates for old Redis system
    updates = {"status": status, "updated_at": timestamp}
    if status == "processing":
        updates["started_at"] = timestamp
    elif status in ["completed", "failed"]:
        updates["completed_at"] = timestamp
    
    updates.update(kwargs)
    
    # Update old Redis system (for backward compatibility)
    redis_client.hset(f"job:{job_id}", mapping={
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in updates.items()
    })
    
    # Update JobRegistry
    registry_updates = {"updated_at": timestamp}
    
    # Map status values for JobRegistry
    if status == "processing":
        registry_updates["status"] = "processing"
    elif status == "completed":
        registry_updates["status"] = "done"
        if "output_file" in kwargs:
            registry_updates["result_path"] = kwargs["output_file"]
    elif status == "failed":
        registry_updates["status"] = "failed"
        if "error" in kwargs:
            registry_updates["error"] = kwargs["error"]
    else:
        registry_updates["status"] = status
    
    # Add any additional fields
    for key, value in kwargs.items():
        if key in ["result_path", "error"]:
            registry_updates[key] = value
    
    # Update JobRegistry in Redis
    try:
        redis_client.hset(
            f"registry:job:{job_id}",
            mapping={k: str(v) if v is not None else "" for k, v in registry_updates.items()}
        )
        logger.debug(f"Updated JobRegistry for {job_id}: {registry_updates}")
    except Exception as e:
        logger.warning(f"Failed to update JobRegistry for {job_id}: {str(e)}")
    
    # Update job indices to keep them current
    try:
        update_job_indices(redis_client, job_id, registry_updates["status"], timestamp)
    except Exception as e:
        logger.warning(f"Failed to update job indices for {job_id}: {str(e)}")

@app.task(bind=True, name='worker.process_lab_report')
def process_lab_report(self, job_id: str):
    """
    Main task: Process lab report through complete pipeline
    
    Pipeline stages:
    1. PDF Extraction
    2. Role Classification  
    3. Header/Specimen/Patient Extraction
    4. Test Row Classification
    5. Panel Composition
    6. Confidence Scoring
    7. JSON Output
    
    Configuration flags (controlled by COMPOSITION_FLAGS and env overrides):
    - LABAI_EXTRACT_META: Enable/disable enhanced metadata extraction (default: 1)
    - LABAI_PANEL_CODE_DETECTION: Enable/disable panel code detection in debug (default: 1)
    - LABAI_PANEL_COMMENT_DETECTION: Enable/disable panel comment detection in debug (default: 1)
    - LABAI_TEST_EXTRAS_DETECTION: Enable/disable test extras in debug (default: 1)
    
    Set env var to "0" to disable a feature, any other value (or unset) enables it.
    """
    start_time = time.time()
    
    try:
        # Update job status
        update_job_status(job_id, "processing")
        log_progress(job_id, "start", "Starting lab report processing")
        
        # Get job data
        job_data = redis_client.hgetall(f"job:{job_id}")
        if not job_data:
            raise ProcessingError("Job data not found")
        
        # Decode job data
        job_info = {}
        for key, value in job_data.items():
            key = key.decode('utf-8') if isinstance(key, bytes) else key
            value = value.decode('utf-8') if isinstance(value, bytes) else value
            
            if key in ['config', 'progress']:
                try:
                    job_info[key] = json.loads(value)
                except:
                    job_info[key] = {}
            else:
                job_info[key] = value
        
        config = job_info.get('config', {})
        
        # Stage 1: Get input PDF
        log_progress(job_id, "input", "Acquiring PDF input", 5)
        pdf_path = get_pdf_input(job_id, job_info)
        
        # Stage 2: PDF Extraction
        log_progress(job_id, "extraction", "Extracting text and layout from PDF", 10)
        lines = extract_pdf(str(pdf_path), config.get('extraction', {}))
        
        # Convert to expected format for downstream processing
        extraction_result = {
            "lines": lines,
            "metadata": {"pdf_path": str(pdf_path)},
            "stats": {
                "total_lines": len(lines),
                "total_pages": len(set(line.get('page', 1) for line in lines)),
            }
        }
        
        # Debug: Write 01_lines
        write_debug_file(job_id, "01_lines", extraction_result)
        
        # Stage 2.5: Pre-processing - Row Cell Merging
        log_progress(job_id, "merge", "Merging row cells", 20)
        from services.worker.preprocess.row_merger import merge_row_cells, debug_dump
        
        # Get merge tolerance from environment
        merge_y_tol = float(os.getenv("MERGE_Y_TOL", "0.006"))
        
        # Preserve original unmerged lines for other modules if needed
        original_lines = extraction_result['lines'].copy()
        
        # Merge row cells for better role classification
        merged_lines = merge_row_cells(extraction_result['lines'], y_tol=merge_y_tol)
        
        # Create merged extraction result for roles classifier
        merged_extraction_result = extraction_result.copy()
        merged_extraction_result['lines'] = merged_lines
        
        # Debug: Write merged lines
        merged_debug_data = {
            "original_line_count": len(original_lines),
            "merged_line_count": len(merged_lines),
            "merge_y_tolerance": merge_y_tol,
            "lines": merged_lines,
            "metadata": extraction_result.get('metadata', {}),
            "stats": extraction_result.get('stats', {})
        }
        write_debug_file(job_id, "01a_lines_merged", merged_debug_data)
        
        # Stage 3: Role Classification (using merged lines)
        log_progress(job_id, "roles", "Classifying line roles", 25)
        merged_role_result = classify_roles(merged_extraction_result, config.get('roles', {}))
        
        # Apply heuristic TEST_ROW detection if needed
        from services.worker.roles.heuristics import tag_rows_heuristic
        from collections import Counter
        
        # Count current TEST_ROW predictions on merged lines
        role_counts = Counter(line.get('predicted_role', 'UNKNOWN') for line in merged_role_result['lines'])
        test_row_count = role_counts.get('TEST_ROW', 0)
        
        # Apply heuristics if < 3 TEST_ROW found
        heuristic_applied = False
        if test_row_count < 3:
            heuristic_indexes = tag_rows_heuristic(merged_role_result['lines'])
            if heuristic_indexes:
                logger.info(f"Applying heuristic TEST_ROW tagging to {len(heuristic_indexes)} lines")
                
                # Update predicted_role for heuristic matches
                for i in heuristic_indexes:
                    if i < len(merged_role_result['lines']):
                        merged_role_result['lines'][i]['predicted_role'] = 'TEST_ROW'
                        # Also update canonical role field
                        merged_role_result['lines'][i]['role'] = 'TEST_ROW'
                
                # Update stats
                merged_role_result['stats']['used_fallback'] = True
                merged_role_result['stats']['fallback_reason'] = f"heuristic TEST_ROW tagging ({len(heuristic_indexes)} lines)"
                merged_role_result['stats']['role_distribution'] = dict(Counter(
                    line.get('predicted_role', 'UNKNOWN') for line in merged_role_result['lines']
                ))
                heuristic_applied = True
        
        # Use merged lines for downstream processing instead of mapping back to original
        role_result = merged_role_result.copy()
        
        # Enhance merged lines with segments information for test-row tagging
        enhanced_lines = []
        for line in role_result['lines']:
            enhanced_line = line.copy()
            
            # Add segments array with geometry info from original cells
            if 'cells' in line:
                segments = []
                for cell in line['cells']:
                    segments.append({
                        'text': cell.get('text', '').strip(),
                        'x_left': cell.get('xLeft', 0.0),
                        'x_right': cell.get('xRight', 0.0),
                        'font_size': cell.get('fontSize', 12.0),
                        'is_bold': cell.get('isBold', False)
                    })
                enhanced_line['segments'] = segments
            
            # Ensure consistent field names for downstream compatibility
            enhanced_line['y_norm'] = enhanced_line.get('yNorm', 0.0)
            enhanced_line['x_left'] = enhanced_line.get('xLeft', 0.0) 
            enhanced_line['x_right'] = enhanced_line.get('xRight', 0.0)
            enhanced_line['font_size'] = enhanced_line.get('fontSize', 12.0)
            enhanced_line['is_bold'] = enhanced_line.get('isBold', False)
            
            enhanced_lines.append(enhanced_line)
        
        role_result['lines'] = enhanced_lines
        
        # Update stats to reflect heuristic application
        if heuristic_applied:
            role_result['stats']['used_fallback'] = merged_role_result['stats']['used_fallback']
            role_result['stats']['fallback_reason'] = merged_role_result['stats']['fallback_reason']
        
        # Build classifier probabilities map for scorer
        classifier_probabilities = {
            i: (float(rec.get('role_prob', 0.0)) if rec.get('predicted_role') == 'TEST_ROW' else 0.0)
            for i, rec in enumerate(role_result.get('lines', []))
        }
        
        # Stage 4: Header/Metadata Extraction
        log_progress(job_id, "headers", "Extracting headers and metadata", 40)
        if COMPOSITION_FLAGS["extract_meta"]:
            header_result = extract_headers(role_result, config.get('headers', {}))
        else:
            # Fallback header extraction without enhanced meta extraction
            header_result = {
                "patient_info": {},
                "specimen_info": {},
                "vendor_info": {},
                "ordering_info": {},
                "report_meta_info": {},
                "stats": {"extract_meta_enabled": False}
            }
        
        # NEW: Enhanced Debug: Write 02_roles with metadata
        if COMPOSITION_FLAGS["extract_meta"]:
            enhanced_roles_debug = enhance_debug_data("02_roles", role_result, header_result=header_result)
        else:
            enhanced_roles_debug = role_result
        write_debug_file(job_id, "02_roles", enhanced_roles_debug)
        
        # Stage 5: Test Row Processing
        log_progress(job_id, "testrows", "Processing test row tokens", 60)
        testrow_result = process_test_rows(role_result, config.get('testrows', {}))
        
        # Stage 6: Panel Composition with Confidence
        log_progress(job_id, "composition", "Composing panels with confidence scoring", 80)
        composition_result = compose_panels(
            testrow_result,
            role_result,
            config.get('composition', {}),
            classifier_probabilities=classifier_probabilities
        )
        
        # NEW: Enhanced Debug: Write 03_compose with panel/test extras
        if COMPOSITION_FLAGS["panel_code_detection"] or COMPOSITION_FLAGS["panel_comment_detection"] or COMPOSITION_FLAGS["test_extras_detection"]:
            enhanced_compose_debug = enhance_debug_data("03_compose", composition_result, composition_result=composition_result)
        else:
            enhanced_compose_debug = composition_result
        write_debug_file(job_id, "03_compose", enhanced_compose_debug)
        
        # Stage 7: Final JSON Output
        log_progress(job_id, "output", "Generating final JSON output", 95)
        output_path = write_output(job_id, composition_result, header_result)
        
        # Complete
        processing_time = time.time() - start_time
        log_progress(job_id, "complete", f"Processing completed in {processing_time:.2f}s", 100)
        
        update_job_status(
            job_id, 
            "completed",
            output_file=str(output_path),
            processing_time=processing_time
        )
        
        # Cleanup temporary files
        cleanup_temp_files(pdf_path)
        
        return {
            "success": True,
            "job_id": job_id,
            "output_file": str(output_path),
            "processing_time": processing_time,
            "summary": composition_result.get("summary", {})
        }
        
    except Exception as e:
        # Handle errors
        processing_time = time.time() - start_time
        error_msg = f"Processing failed: {str(e)}"
        error_stack = traceback.format_exc()
        
        log_progress(job_id, "error", error_msg, extra_data={
            "error_type": type(e).__name__,
            "traceback": error_stack
        })
        
        # Create detailed error message with stack trace
        detailed_error = f"{error_msg}\n\nStack trace:\n{error_stack}"
        
        update_job_status(
            job_id,
            "failed", 
            error=detailed_error,
            processing_time=processing_time
        )
        
        # Cleanup
        try:
            if 'pdf_path' in locals():
                cleanup_temp_files(pdf_path)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup failed: {str(cleanup_error)}")
        
        logger.error(f"Job {job_id} failed: {error_msg}")
        logger.error(error_stack)
        
        # Don't retry - mark as permanently failed
        raise e

def get_pdf_input(job_id: str, job_info: Dict[str, Any]) -> Path:
    """Get PDF input from upload or URL"""
    
    if job_info.get('source') == 'upload':
        # File was uploaded
        input_file = Path(job_info['input_file'])
        if not input_file.exists():
            raise ProcessingError(f"Uploaded file not found: {input_file}")
        return input_file
    
    elif job_info.get('source') == 'url':
        # Download from URL
        pdf_url = job_info['pdf_url']
        temp_path = TEMP_DIR / f"{job_id}_input.pdf"
        
        try:
            response = requests.get(pdf_url, timeout=300, stream=True)
            response.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return temp_path
            
        except Exception as e:
            raise ProcessingError(f"Failed to download PDF from URL: {str(e)}")
    
    else:
        raise ProcessingError("No valid input source specified")

def _call_extractor(extractor: PDFExtractor, pdf_path: str) -> List[Dict]:
    """
    Call whatever method the extractor exposes and return a list[dict] lines.
    Supported: extract, extract_lines, run, __call__.
    """
    for name in ("extract", "extract_lines", "run"):
        if hasattr(extractor, name) and callable(getattr(extractor, name)):
            return getattr(extractor, name)(pdf_path)

    if callable(extractor):
        return extractor(pdf_path)

    raise ProcessingError(
        f"PDFExtractor has no supported extract method. "
        f"Callables: {[n for n in dir(extractor) if not n.startswith('_') and callable(getattr(extractor, n, None))]}"
    )


def _apply_header_quarantine_safely(lines):
    """
    Improved header/footer quarantine that only removes lines if they repeat across pages
    and are in the top/bottom 10% of page area.
    """
    try:
        body, hdr = _quarantine_headers_footers_improved(lines)
        return (body or lines), (hdr or [])
    except Exception:
        return lines, []


def _quarantine_headers_footers_improved(lines: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """
    Improved header/footer quarantine logic:
    - Only quarantine lines in top/bottom 10% of pages
    - Must repeat across >= 2 pages with >= 0.85 similarity
    - Don't remove one-off headers like "COMPREHENSIVE METABOLIC PANEL"
    """
    if len(lines) < 10:
        return lines, []
    
    # Group lines by page and position
    pages = {}
    for line in lines:
        page = line.get('page', 1)
        if page not in pages:
            pages[page] = []
        pages[page].append(line)
    
    if len(pages) < 2:
        return lines, []  # Need at least 2 pages for cross-page analysis
    
    # Find potential header/footer candidates (top/bottom 10%)
    candidates = []
    for page_num, page_lines in pages.items():
        for line in page_lines:
            y_norm = line.get('yNorm', line.get('y_norm', 0.5))
            # Top 10% (y_norm > 0.9) or bottom 10% (y_norm < 0.1)
            if y_norm > 0.9 or y_norm < 0.1:
                candidates.append(line)
    
    # Find repeating patterns across pages
    quarantined = set()
    
    for i, candidate in enumerate(candidates):
        if id(candidate) in quarantined:
            continue
            
        candidate_text = candidate.get('text', '').strip().lower()
        candidate_page = candidate.get('page', 1)
        candidate_y = candidate.get('yNorm', candidate.get('y_norm', 0.5))
        
        # Find similar lines on other pages
        matches = [candidate]
        
        for other in candidates[i+1:]:
            if id(other) in quarantined:
                continue
                
            other_page = other.get('page', 1)
            if other_page == candidate_page:
                continue  # Same page
                
            other_text = other.get('text', '').strip().lower()
            other_y = other.get('yNorm', other.get('y_norm', 0.5))
            
            # Check similarity and position
            similarity = _text_similarity(candidate_text, other_text)
            position_diff = abs(candidate_y - other_y)
            
            if similarity >= 0.85 and position_diff < 0.1:
                matches.append(other)
        
        # If found on >= 2 pages, quarantine all matches
        if len(set(match.get('page', 1) for match in matches)) >= 2:
            # But don't quarantine obvious panel headers
            if not _is_likely_panel_header(candidate_text):
                for match in matches:
                    quarantined.add(id(match))
    
    # Separate quarantined from body
    body = [line for line in lines if id(line) not in quarantined]
    headers = [line for line in lines if id(line) in quarantined]
    
    return body, headers


def _text_similarity(text1: str, text2: str) -> float:
    """Calculate shingled similarity between two texts"""
    if not text1 or not text2:
        return 0.0
    
    if text1 == text2:
        return 1.0
    
    # Simple word-based similarity
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union)


def _is_likely_panel_header(text: str) -> bool:
    """Check if text looks like a panel header that shouldn't be quarantined"""
    panel_indicators = [
        'comprehensive metabolic panel', 'cmp', 'complete blood count', 'cbc',
        'lipid panel', 'liver function', 'kidney function', 'thyroid',
        'basic metabolic panel', 'bmp', 'electrolytes', 'chemistry'
    ]
    
    text_lower = text.lower()
    return any(indicator in text_lower for indicator in panel_indicators)


# ============================================================================
# Test-Row CRF Model Implementation
# ============================================================================

# Known medical units for validation
KNOWN_UNITS = {
    # Core list (case-insensitive; punctuation around edges ignored)
    "mg/dl", "g/dl", "mmol/l", "uiu/ml", "iu/l", "ng/ml", "pg/ml", "u/l",
    "k/ul", "m/ul", "%",
    # A few extras commonly seen
    "mcg/dl", "ug/dl", "mg/l", "g/l", "copies/ml", "fl", "pg", "iu"
}

def _normalize_unit_token(token: str) -> str:
    """Lowercase and strip leading/trailing punctuation/whitespace without removing internal slashes."""
    if token is None:
        return ""
    t = str(token)
    # Strip leading/trailing common punctuation but keep internal separators like '/'
    t = re.sub(r'^[\s\.,;:()\[\]{}<>\-\+]+|[\s\.,;:()\[\]{}<>\-\+]+$', '', t)
    return t.lower()

def is_unit_like(token: str) -> bool:
    """Check if a token looks like a medical unit (case-insensitive, ignores edge punctuation)."""
    if not token:
        return False
    normalized = _normalize_unit_token(token)
    return normalized in KNOWN_UNITS

def _try_load_testrow_model(model_dir: str = None) -> dict:
    """
    Internal loader for Test-Row CRF tagger.
    
    Preference order for artifacts (first found is used):
      - model.crf
      - crf.joblib
      - model.joblib
    
    Label resolution preference:
      1) metadata.json in same directory using one of keys: ["labels", "label_list", "classes"]
      2) model.classes_ attribute
      3) default BIO labels
    
    Does NOT require label_encoder.pkl.
    
    Returns:
        dict with keys: model, labels
        Empty dict on any error
    """
    if model_dir is None:
        model_dir = os.getenv("MODEL_TESTROW_DIR", "/models/testrow")
    
    model_dir_path = Path(model_dir)
    if not model_dir_path.exists():
        return {}
    
    # Try to load the CRF model per preference order
    pipeline = None
    model_filename_used = None
    for model_filename in ["model.crf", "crf.joblib", "model.joblib"]:
        model_path = model_dir_path / model_filename
        if model_path.exists():
            try:
                pipeline = joblib.load(str(model_path))
                model_filename_used = model_filename
                logger.info(f"Loaded Test-Row CRF from '{model_filename}' in {model_dir_path}")
                break
            except Exception as e:
                logger.warning(f"Failed to load {model_filename}: {e}")
                continue
    
    if pipeline is None:
        logger.warning(f"No CRF model found in {model_dir_path}")
        return {}
    
    # Prefer labels from metadata.json
    labels = None
    labels_source = None
    metadata_path = model_dir_path / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            for key in ["labels", "label_list", "classes"]:
                if isinstance(metadata.get(key), list):
                    labels = list(metadata[key])
                    labels_source = f"metadata.json:{key}"
                    logger.info(f"Resolved {len(labels)} labels from {labels_source}")
                    break
        except Exception as e:
            logger.warning(f"Could not read metadata.json: {e}")

    # Next, derive labels from pipeline.classes_
    if labels is None and hasattr(pipeline, 'classes_'):
        try:
            labels = list(pipeline.classes_)
            labels_source = "model.classes_"
            logger.info(f"Resolved {len(labels)} labels from model.classes_")
        except Exception as e:
            logger.warning(f"Could not derive labels from model.classes_: {e}")
    
    # Final fallback to default labels
    if labels is None:
        labels = [
            "O",
            "B-TEST_NAME", "I-TEST_NAME",
            "B-VALUE", "I-VALUE",
            "B-UNIT", "I-UNIT",
            "B-REF_RANGE", "I-REF_RANGE",
            "B-FLAG", "I-FLAG",
        ]
        labels_source = "default"
        logger.info(f"Using default {len(labels)} labels (no metadata/classes_)")
    
    return {
        "pipeline": pipeline,
        "labels": labels,
        "model_file": model_filename_used,
        "labels_source": labels_source,
    }

def load_testrow_model(force: bool = False):
    """Load Test-Row model via adapter from MODEL_TESTROW_DIR."""
    global _testrow_model, _testrow_model_ok, _testrow_used_fallback_last, _testrow_labels, _testrow_pipeline
    if _testrow_model is not None and not force:
        return

    model_dir = os.getenv("MODEL_TESTROW_DIR", str(TESTROW_MODEL_DIR))

    try:
        adapter = load_testrow_adapter(model_dir)
        if adapter is None:
            _testrow_model = None
            _testrow_model_ok = False
            _testrow_pipeline = None
            _testrow_used_fallback_last = True
            logger.info(f"[worker] TestRow model not found in {model_dir}; using fallback")
            return
        _testrow_model = adapter
        _testrow_labels = list(getattr(adapter, "labels", []) or [])
        # Initialize/refresh module-level pipeline as the single source of truth
        _testrow_pipeline = build_testrow_pipeline()
        _testrow_model_ok = _testrow_pipeline is not None
        _testrow_used_fallback_last = False
        logger.info(f"[worker] TestRow model loaded via adapter from {model_dir}")
    except Exception as e:
        _testrow_model = None
        _testrow_pipeline = None
        _testrow_model_ok = False
        _testrow_used_fallback_last = True
        logger.warning(f"[worker] TestRow model load FAILED from {model_dir}: {e}")

def _predict_testrow_tags(tokens):
    """
    Return a BIO tag per token.
    If CRF loaded, use it; else fallback to rule-based splitter.
    """
    # tokens is a list of strings or a list of dicts with "token"
    toks = [t["token"] if isinstance(t, dict) and "token" in t else str(t) for t in tokens]

    # if CRF available
    if globals().get("_testrow_model_ok") and globals().get("_testrow_crf") is not None:
        # Basic featureizer to mirror training-time style. Keep simple & robust.
        def feats(seq, i):
            w = seq[i]
            f = {
                "bias": 1.0,
                "w.lower()": w.lower(),
                "w.isdigit()": w.isdigit(),
                "w.hasdigit": any(ch.isdigit() for ch in w),
                "w.has%": "%" in w,
                "w.has/": "/" in w,
                "w.has-": "-" in w,
                "w.sfx2": w[-2:] if len(w) >= 2 else w,
                "w.pfx2": w[:2],
            }
            if i > 0:
                wp = seq[i-1]
                f.update({
                    "-1.lower": wp.lower(),
                    "-1.hasdigit": any(ch.isdigit() for ch in wp),
                    "-1.has/": "/" in wp,
                    "-1.has-": "-" in wp,
                })
            else:
                f["BOS"] = True
            if i < len(seq)-1:
                wn = seq[i+1]
                f.update({
                    "+1.lower": wn.lower(),
                    "+1.hasdigit": any(ch.isdigit() for ch in wn),
                    "+1.has/": "/" in wn,
                    "+1.has-": "-" in wn,
                })
            else:
                f["EOS"] = True
            return f

        X = [[feats(toks, i) for i in range(len(toks))]]
        y_pred = globals()["_testrow_crf"].predict(X)[0]
        globals()["_testrow_used_fallback_last"] = False
        return y_pred

    # fallback
    globals()["_testrow_used_fallback_last"] = True
    # naive heuristic: number→B-VALUE, unit tokens, range with '-' or '/'
    tags = ["O"] * len(toks)
    # test name ← everything up to the first obvious value/unit/range
    boundary = len(toks)
    for i, w in enumerate(toks):
        lw = w.lower()
        if w.replace(".", "", 1).isdigit() or any(ch.isdigit() for ch in w):
            tags[i] = "B-VALUE"; boundary = min(boundary, i); break
        if any(u in lw for u in ["mg/dl", "mmol/l", "g/dl", "iu/l", "u/l", "ng/ml", "pg/ml", "fl", "k/u", "10^", "%"]):
            tags[i] = "B-UNIT"; boundary = min(boundary, i); break
        if "-" in w or "/" in w:
            tags[i] = "B-REF_RANGE"; boundary = min(boundary, i); break
    for j in range(boundary):
        tags[j] = "I-TEST_NAME" if j > 0 else "B-TEST_NAME"
    return tags

# Back-compat alias if older callers import private name
try:
    _load_testrow_model
except NameError:
    _load_testrow_model = load_testrow_model

# Helper functions for robust test-row tagging
def _tok_with_spans(s: str):
    toks = []
    i = 0
    for part in s.split():
        start = s.find(part, i)
        end = start + len(part)
        toks.append({"token": part, "start_pos": start, "end_pos": end})
        i = end
    return toks

def _feat(seq, i):
    w = seq[i]
    f = {
        "bias": 1.0,
        "w.lower": w.lower(),
        "w.isdigit": w.isdigit(),
        "w.hasdigit": any(ch.isdigit() for ch in w),
        "w.has%": "%" in w,
        "w.has/": "/" in w,
        "w.has-": "-" in w,
        "w.sfx2": w[-2:] if len(w) >= 2 else w,
        "w.pfx2": w[:2],
    }
    if i > 0:
        wp = seq[i-1]
        f.update({
            "-1.lower": wp.lower(),
            "-1.hasdigit": any(ch.isdigit() for ch in wp),
            "-1.has/": "/" in wp,
            "-1.has-": "-" in wp,
        })
    else:
        f["BOS"] = True
    if i < len(seq) - 1:
        wn = seq[i+1]
        f.update({
            "+1.lower": wn.lower(),
            "+1.hasdigit": any(ch.isdigit() for ch in wn),
            "+1.has/": "/" in wn,
            "+1.has-": "-" in wn,
        })
    else:
        f["EOS"] = True
    return f

def _fallback_tags(tokens_str):
    # simple heuristic for when model isn't loaded
    tags = ["O"] * len(tokens_str)
    boundary = len(tokens_str)
    for i, w in enumerate(tokens_str):
        lw = w.lower()
        if w.replace(".", "", 1).isdigit() or any(ch.isdigit() for ch in w):
            tags[i] = "B-VALUE"; boundary = min(boundary, i); break
        if any(u in lw for u in ["mg/dl","mmol/l","g/dl","iu/l","u/l","ng/ml","pg/ml","fl","k/u","10^","%"]):
            tags[i] = "B-UNIT"; boundary = min(boundary, i); break
        if "-" in w or "/" in w:
            tags[i] = "B-REF_RANGE"; boundary = min(boundary, i); break
    for j in range(min(boundary, len(tokens_str))):
        tags[j] = "I-TEST_NAME" if j > 0 else "B-TEST_NAME"
    return tags

def _parse_fields(tokens, tags):
    # build fields from BIO tags
    def collect(label):
        buf = []
        for t, g in zip(tokens, tags):
            if g.endswith(label):
                buf.append(t["token"])
        return buf
    name_parts = []
    val = None
    unit = None
    ref_parts = []
    flags = []

    # test name: contiguous B/I-TEST_NAME at start
    saw_name = False
    for t, g in zip(tokens, tags):
        if g in ("B-TEST_NAME","I-TEST_NAME"):
            name_parts.append(t["token"])
            saw_name = True
        elif saw_name:
            break

    # first VALUE / UNIT / REF_RANGE / FLAG
    for t, g in zip(tokens, tags):
        if val is None and g in ("B-VALUE","I-VALUE"):
            val = t["token"]
        if unit is None and g in ("B-UNIT","I-UNIT"):
            unit = t["token"]
        if g in ("B-REF_RANGE","I-REF_RANGE"):
            ref_parts.append(t["token"])
        if g in ("B-FLAG","I-FLAG"):
            flags.append(t["token"])

    fields = {
        "test_name": " ".join(name_parts).strip() or None,
        "result_value": val,
        "units": unit,
        "reference_range": " ".join(ref_parts).strip() or None,
        "flags": flags or None
    }
    return fields

def tag_testrow_tokens(tokens: list[str]) -> list[str]:
    """
    Public tagging helper for Test-Row tokens.
    
    Args:
        tokens: List of token strings
    
    Returns:
        List of BIO label strings (same length as tokens)
    """
    if not tokens:
        return []
    
    # Use the new CRF-based tagger first
    bio_labels = _predict_testrow_tags(tokens)
    if bio_labels:
        return bio_labels
    
    # Fallback if _predict_testrow_tags returns empty (shouldn't happen)
    globals()["_testrow_used_fallback_last"] = True
    return _fallback_testrow_tokens(tokens)

def _fallback_tag_testrow_line(text: str, confidence: float = 0.7):
    """
    Simple regex/heuristic fallback for test-row tagging when model is not available.
    Does crude parsing but ensures resilience.
    """
    if not text or not text.strip():
        return {
            "text": text or "",
            "tokens": [],
            "parsed_fields": {
                "test_name": None,
                "result_value": None,
                "units": None,
                "reference_range": None,
                "flags": []
            }
        }
    
    import re
    
    # Tokenize on whitespace with positions
    tokens = []
    words = text.split()
    current_pos = 0
    
    for word in words:
        start = text.find(word, current_pos)
        if start == -1:
            start = current_pos
        end = start + len(word)
        tokens.append({
            "token": word,
            "start_pos": start,
            "end_pos": end
        })
        current_pos = end
    
    # Simple heuristic tagging
    parsed_fields = {
        "test_name": None,
        "result_value": None,
        "units": None,
        "reference_range": None,
        "flags": []
    }
    
    out_tokens = []
    test_name_parts = []
    
    for i, token_info in enumerate(tokens):
        word = token_info["token"]
        tag = "O"
        
        # Check for numeric values
        if re.match(r'^\d+\.?\d*$', word) and parsed_fields["result_value"] is None:
            tag = "B-VALUE"
            parsed_fields["result_value"] = word
        # Check for units
        elif word.lower() in ['mg/dl', 'mmol/l', 'g/dl', 'iu/l', 'u/l', 'ng/ml', 'pg/ml', 'fl', 'k/ul', '%']:
            tag = "B-UNIT"
            parsed_fields["units"] = word
        # Check for reference ranges
        elif re.match(r'^\d+\.?\d*[-–]\d+\.?\d*$', word):
            tag = "B-REF_RANGE"
            parsed_fields["reference_range"] = word
        # Check for flags
        elif word.upper() in ['H', 'L', 'HIGH', 'LOW', 'CRITICAL', 'ABNORMAL']:
            tag = "B-FLAG"
            parsed_fields["flags"].append(word.upper())
        # Everything else goes to test name until we hit a value
        elif parsed_fields["result_value"] is None:
            tag = "I-TEST_NAME" if test_name_parts else "B-TEST_NAME"
            test_name_parts.append(word)
        
        out_tokens.append({
            "token": word,
            "tag": tag,
            "confidence": confidence,
            "start_pos": token_info["start_pos"],
            "end_pos": token_info["end_pos"]
        })
    
    # Join test name parts
    if test_name_parts:
        parsed_fields["test_name"] = " ".join(test_name_parts)
    
    # Convert flags list to expected format
    if not parsed_fields["flags"]:
        parsed_fields["flags"] = []
    
    # Try improved rule-based parse for parsed_fields + warnings
    try:
        from services.worker.parsing.testrow_rules import parse_line as rb_parse
        rb = rb_parse(text)
        pf = rb.get("parsed_fields", {}) if isinstance(rb, dict) else {}
        # Only override fields we could parse
        for k in ("test_name", "result_value", "units", "reference_range", "flags"):
            v = pf.get(k)
            if v is not None:
                parsed_fields[k] = v
        out = {"text": text, "tokens": out_tokens, "parsed_fields": parsed_fields}
        if "fieldWarnings" in rb:
            out["fieldWarnings"] = rb["fieldWarnings"]
        return out
    except Exception:
        # If rules parser fails, return basic result
        return {
            "text": text,
            "tokens": out_tokens,
            "parsed_fields": parsed_fields
        }

def _ensure_testrow_pipeline() -> bool:
    """Ensure the module-level testrow pipeline is initialized."""
    global _testrow_pipeline, _testrow_model_ok
    if _testrow_pipeline is None:
        _testrow_pipeline = build_testrow_pipeline()
    _testrow_model_ok = _testrow_pipeline is not None
    return _testrow_pipeline is not None


def tag_testrow_line(text: str):
    """
    Returns:
    {
      "text": <str>,
      "tokens": [{"token","tag","confidence","start_pos","end_pos"}, ...],
      "parsed_fields": {...}
    }
    """
    # If pipeline not loaded, try to (re)initialize, else fallback
    if not _ensure_testrow_pipeline():
        return _fallback_tag_testrow_line(text, confidence=0.7)

    tokens = _tok_with_spans(text)
    toks_str = [t["token"] for t in tokens]

    try:
        tags = _testrow_pipeline.predict(toks_str) or []
        if len(tags) != len(toks_str):
            return _fallback_tag_testrow_line(text, confidence=0.7)
        probas = _testrow_pipeline.predict_proba(toks_str) or [{} for _ in toks_str]
        _testrow_used_fallback_last = False
    except Exception:
        return _fallback_tag_testrow_line(text, confidence=0.7)

    out_tokens = []
    for i, (t, tag) in enumerate(zip(tokens, tags)):
        dist = probas[i] if i < len(probas) and isinstance(probas[i], dict) else {}
        conf = float(dist.get(tag, 0.9)) if tag in dist else 0.9
        out_tokens.append({
            "token": t["token"],
            "tag": tag,
            "confidence": conf,
            "start_pos": t["start_pos"],
            "end_pos": t["end_pos"],
        })

    parsed = _parse_fields(tokens, tags)
    # Normalize flags: High/HIGH -> H, Low/LOW -> L
    try:
        flags = parsed.get("flags")
        if isinstance(flags, list):
            norm = []
            for f in flags:
                fl = str(f).strip()
                if fl.lower() == "high":
                    norm.append("H")
                elif fl.lower() == "low":
                    norm.append("L")
                else:
                    norm.append(fl)
            parsed["flags"] = norm
    except Exception:
        pass
    
    # NEW: Extract enhanced fields using normalize helpers
    try:
        # Extract LOINC/CPT codes
        codes = {}
        code_pattern = re.compile(r'\b(LOINC|CPT)\s*[:#]?\s*([A-Z0-9-]+)\b', re.IGNORECASE)
        code_matches = code_pattern.findall(text)
        for code_type, code_value in code_matches:
            codes[code_type.lower()] = code_value
        if codes:
            parsed['codes'] = codes
        
        # Extract methodology using keywords
        method_patterns = [
            r'(?:Method|Methodology)[\s:]*([^,\n]+)',
            r'\b(Immunoassay|LC/MS-MS|LC-MS|HPLC|RIA|ELISA|PCR|Flow Cytometry|Microscopy)\b'
        ]
        for pattern in method_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                parsed['methodology'] = match.group(1).strip()
                break
        
        # Extract observation time
        time_patterns = [
            r'\b(\d{1,2}:\d{2}\s*(?:AM|PM))\b',  # 12-hour format
            r'\b(\d{1,2}:\d{2})\b'  # 24-hour format
        ]
        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                time_str = match.group(1)
                # Try to normalize to ISO format if it's a full timestamp
                # For now, just store the extracted time string
                parsed['observed_at'] = time_str
                break
        
        # Extract comments/notes - look for remaining meaningful text
        # Simple heuristic: text after known field patterns might be comments
        comment_text = text
        
        # Remove known field patterns to isolate potential comments
        if parsed.get('test_names'):
            for name in parsed['test_names']:
                comment_text = comment_text.replace(str(name), '').strip()
        if parsed.get('values'):
            for value in parsed['values']:
                comment_text = comment_text.replace(str(value), '').strip()
        if parsed.get('units'):
            for unit in parsed['units']:
                comment_text = comment_text.replace(str(unit), '').strip()
        if parsed.get('ref_ranges'):
            for range_val in parsed['ref_ranges']:
                comment_text = comment_text.replace(str(range_val), '').strip()
        if parsed.get('flags'):
            for flag in parsed['flags']:
                comment_text = comment_text.replace(str(flag), '').strip()
        
        # Remove codes and methodology from comment text
        if 'codes' in parsed:
            for code_type, code_value in parsed['codes'].items():
                comment_text = re.sub(f'\\b{code_type}\\s*[:#]?\\s*{re.escape(code_value)}\\b', '', comment_text, flags=re.IGNORECASE)
        if 'methodology' in parsed:
            method = parsed['methodology']
            comment_text = comment_text.replace(method, '').strip()
        if 'observed_at' in parsed:
            time_val = parsed['observed_at']
            comment_text = comment_text.replace(time_val, '').strip()
        
        # Clean up and check if meaningful comment remains
        comment_text = re.sub(r'[^\w\s]', ' ', comment_text)
        comment_text = re.sub(r'\s+', ' ', comment_text).strip()
        if len(comment_text) > 5 and not re.match(r'^\d+\.?\d*$', comment_text):
            # Additional filter: check if it looks like a meaningful comment
            words = comment_text.split()
            if len(words) >= 2 and any(len(word) > 3 for word in words):
                parsed['comments'] = comment_text
                
    except Exception:
        # Don't crash if enhanced extraction fails
        pass
    
    return {"text": text, "tokens": out_tokens, "parsed_fields": parsed}

def testrow_loaded_state():
    return {
        "ok": _testrow_model_ok,
        "has_model": _testrow_model is not None,
        "used_fallback_last": _testrow_used_fallback_last,
    }

def _fallback_testrow_tokens(tokens: list[str]) -> list[str]:
    """
    Fallback regex splitter for Test-Row tokens.
    
    Applies greedy left-to-right heuristics:
    - Greedy left chunk → TEST_NAME until first number
    - Next numeric chunk → VALUE
    - Next token in unit whitelist → UNIT (optional)
    - Any trailing patterns → REF_RANGE / FLAG
    """
    if not tokens:
        return []
    
    labels = ["O"] * len(tokens)
    i = 0
    n = len(tokens)
    
    # Unit whitelist
    unit_patterns = {
        "mg/dl", "g/dl", "mmol/l", "iu/l", "k/ul", "m/ul", "ng/ml", "pg/ml", "u/l",
        "%", "mm", "cm", "mg", "g", "ml", "l", "units", "iu", "copies/ml"
    }
    
    # 1. Greedy left chunk → TEST_NAME until first number
    while i < n and not re.match(r'^\d+\.?\d*$', tokens[i]):
        if i == 0:
            labels[i] = "B-TEST_NAME"
        else:
            labels[i] = "I-TEST_NAME"
        i += 1
    
    # 2. Next numeric chunk → VALUE
    if i < n and re.match(r'^\d+\.?\d*$', tokens[i]):
        labels[i] = "B-VALUE"
        i += 1
        # Continue value if next tokens are also numeric
        while i < n and re.match(r'^\d+\.?\d*$', tokens[i]):
            labels[i] = "I-VALUE"
            i += 1
    
    # 3. Next token in unit whitelist → UNIT
    if i < n and tokens[i].lower() in unit_patterns:
        labels[i] = "B-UNIT"
        i += 1
    
    # 4. Process remaining tokens for REF_RANGE and FLAG
    while i < n:
        token = tokens[i].lower()
        
        # Reference range patterns: "70–99", "≤", ">=", "<", ">"
        if (re.match(r'^\d+[–-]\d+$', token) or 
            token in {"≤", "<", ">", ">="} or
            re.match(r'^\d+\.?\d*[–-]\d+\.?\d*$', token)):
            labels[i] = "B-REF_RANGE"
            i += 1
            # Continue ref range
            while i < n and (re.match(r'^\d+', tokens[i]) or tokens[i].lower() in {"-", "–", "to"}):
                labels[i] = "I-REF_RANGE"
                i += 1
        # Flag patterns: "(H/L)", "H", "L", "*", "HIGH", "LOW", "NORMAL"
        elif (re.match(r'^\([HL]\)$', token, re.IGNORECASE) or
              token in {"h", "l", "*", "high", "low", "normal", "abnormal"}):
            labels[i] = "B-FLAG"
            i += 1
        else:
            # Unknown trailing token, skip
            labels[i] = "O"
            i += 1
    
    return labels

# --- CRF-based TEST_ROW tagging utilities ---
def _tokenize_simple(text: str) -> List[str]:
    """Whitespace-ish tokenizer for CRF input."""
    return re.findall(r"\S+", text or "")

def _tok2feats(tokens: List[str], i: int) -> Dict[str, Any]:
    """Feature extractor consistent with trainer/testrow/train_testrow.py"""
    w = tokens[i]
    def shape(s: str) -> str:
        return "".join(
            "A" if c.isupper() else "a" if c.islower() else "9" if c.isdigit() else c
            for c in s
        )[:6]

    feats: Dict[str, Any] = {
        "bias": 1.0,
        "w.lower": w.lower(),
        "w.isdigit": w.isdigit(),
        "w.isalpha": w.isalpha(),
        "w.isalnum": w.isalnum(),
        "pref1": w[:1].lower(),
        "pref2": w[:2].lower(),
        "suf1": w[-1:].lower(),
        "suf2": w[-2:].lower(),
        "shape": shape(w),
    }
    if i > 0:
        p = tokens[i - 1]
        feats.update({"-1:lower": p.lower(), "-1:shape": shape(p)})
    else:
        feats["BOS"] = True
    if i < len(tokens) - 1:
        n = tokens[i + 1]
        feats.update({"+1:lower": n.lower(), "+1:shape": shape(n)})
    else:
        feats["EOS"] = True
    return feats

def _sent2feats(tokens: List[str]) -> List[Dict[str, Any]]:
    return [_tok2feats(tokens, i) for i in range(len(tokens))]

def _bio_to_fields(tokens: List[str], tags: List[str]) -> Dict[str, Any]:
    """Convert BIO tags to coarse fields: test_name, result_value, units, reference_range, flags.

    Picks the first/longest span where multiple occur. Flags are returned as a list.
    """
    spans: Dict[str, List[List[str]]] = {
        "TEST_NAME": [],
        "VALUE": [],
        "UNIT": [],
        "REF_RANGE": [],
        "FLAG": [],
    }
    cur_label: Optional[str] = None
    cur_tokens: List[str] = []

    def flush():
        nonlocal cur_label, cur_tokens
        if cur_label and cur_tokens:
            spans[cur_label].append(cur_tokens)
        cur_label, cur_tokens = None, []

    for tok, tag in zip(tokens, tags):
        if not tag or tag == "O":
            flush()
            continue
        if tag.startswith("B-"):
            flush()
            cur_label = tag[2:]
            cur_tokens = [tok]
        elif tag.startswith("I-"):
            lab = tag[2:]
            if cur_label == lab:
                cur_tokens.append(tok)
            else:
                # Start a new span if misaligned I- label
                flush()
                cur_label = lab
                cur_tokens = [tok]
        else:
            flush()
    flush()

    # Choose representative strings
    def pick_first_or_longest(spans_list: List[List[str]]) -> Optional[str]:
        if not spans_list:
            return None
        # Prefer longest by token count, tie-break by earliest occurrence
        spans_list_sorted = sorted(spans_list, key=lambda s: (-len(s),))
        return " ".join(spans_list_sorted[0]).strip() or None

    fields: Dict[str, Any] = {}
    fields["test_name"] = pick_first_or_longest(spans["TEST_NAME"]) or None
    fields["result_value"] = pick_first_or_longest(spans["VALUE"]) or None
    fields["units"] = pick_first_or_longest(spans["UNIT"]) or None
    fields["reference_range"] = pick_first_or_longest(spans["REF_RANGE"]) or None
    # Flags: keep all spans as list of strings, unique while preserving order
    flag_strings = [" ".join(s).strip() for s in spans["FLAG"] if s]
    seen = set()
    flags_dedup: List[str] = []
    for fs in flag_strings:
        if fs and fs not in seen:
            seen.add(fs)
            flags_dedup.append(fs)
    if flags_dedup:
        fields["flags"] = flags_dedup

    return fields


def _extract_lines_pdfminer_basic(pdf_path: str):
    """
    Minimal, robust pdfminer walker that returns a list of line dicts:
    {page, text, xLeft, xRight, yNorm(0..1 top->bottom), fontSize, isBold, hasText}
    """
    laparams = LAParams(char_margin=2.0, line_margin=0.3, word_margin=0.1, all_texts=True)
    lines = []
    page_no = 0
    for layout in extract_pages(pdf_path, laparams=laparams):
        page_no += 1
        # layout.bbox = (x0,y0,x1,y1) with y increasing upwards; we normalize vertically
        x0, y0, x1, y1 = getattr(layout, "bbox", (0, 0, 1, 1))
        h = max(y1 - y0, 1.0)
        for obj in getattr(layout, "_objs", []):
            if isinstance(obj, LTTextContainer):
                for line in getattr(obj, "_objs", []):
                    if isinstance(line, (LTTextLine, LTTextLineHorizontal)):
                        txt = (line.get_text() or "").strip()
                        if not txt:
                            continue
                        bx0, by0, bx1, by1 = getattr(line, "bbox", (0, 0, 0, 0))
                        y_mid = (by0 + by1) / 2.0
                        y_norm = 1.0 - (y_mid / h)  # 0=top, 1=bottom
                        sizes, is_bold = [], False
                        for ch in getattr(line, "_objs", []):
                            if isinstance(ch, LTChar):
                                sizes.append(getattr(ch, "size", 0) or 0)
                                fn = str(getattr(ch, "fontname", "")).lower()
                                if "bold" in fn or "black" in fn or "heavy" in fn:
                                    is_bold = True
                        font_size = float(sum(sizes) / len(sizes)) if sizes else 0.0
                        lines.append({
                            "page": page_no,
                            "text": txt,
                            "xLeft": float(bx0),
                            "xRight": float(bx1),
                            "yNorm": float(y_norm),
                            "fontSize": font_size,
                            "isBold": bool(is_bold),
                            "hasText": True,
                        })
    return lines


def extract_pdf(pdf_path: str, config: dict) -> List[Dict]:
    """
    Returns list[dict] of lines. Never raises 'no text' if pdfminer clearly produced text but
    a heuristic later over-pruned it.
    """
    dpi = int(config.get("dpi", 150))

    # 1) pdfminer path
    raw = _extract_lines_pdfminer_basic(pdf_path)
    raw_chars = sum(len((l.get("text") or "").strip()) for l in raw)

    if raw and raw_chars >= 20:
        safe_body, _hdr = _apply_header_quarantine_safely(raw)
        if safe_body:
            return safe_body
        # quarantine over-pruned; fall back to returning raw instead of pretending it's empty
        return raw

    # 2) OCR fallback (use existing implementation if you already have one)
    # If you have a function already, call it; otherwise leave your existing OCR code here.
    ocr_lines = []
    try:
        # === BEGIN: hook into your existing OCR path ===
        # Try to use existing PDFExtractor for OCR fallback
        ctor_kwargs = {}
        sig = inspect.signature(PDFExtractor.__init__)
        if "raster_dpi" in sig.parameters:
            ctor_kwargs["raster_dpi"] = max(dpi, 200)
        elif "dpi" in sig.parameters:
            ctor_kwargs["dpi"] = max(dpi, 200)
        if "ocr_mode" in sig.parameters:
            ctor_kwargs["ocr_mode"] = "force"
        
        extractor = PDFExtractor(**ctor_kwargs)
        line_data_objects = _call_extractor(extractor, pdf_path)
        
        # Convert to dict format
        for line_data in line_data_objects:
            if hasattr(line_data, 'text'):  # LineData object
                ocr_lines.append({
                    'text': line_data.text,
                    'page': line_data.page,
                    'xLeft': line_data.xLeft,
                    'xRight': line_data.xRight,
                    'yNorm': line_data.yNorm,
                    'fontSize': line_data.fontSize,
                    'isBold': line_data.isBold,
                    'hasText': line_data.hasText,
                })
            else:  # Already dict format
                ocr_lines.append(line_data)
        # === END: hook ===
    except Exception:
        ocr_lines = []

    ocr_chars = sum(len((l.get("text") or "").strip()) for l in ocr_lines)
    if ocr_lines and ocr_chars >= 10:
        safe_body, _hdr = _apply_header_quarantine_safely(ocr_lines)
        return safe_body or ocr_lines

    # 3) Still nothing useful: drop a tiny debug blob and raise
    try:
        from pathlib import Path
        import json
        Path("/data/outbox").mkdir(parents=True, exist_ok=True)
        Path(f"/data/outbox/{Path(pdf_path).stem}.lines.debug.json").write_text(
            json.dumps({
                "raw_count": len(raw),
                "raw_chars": raw_chars,
                "ocr_count": len(ocr_lines),
                "ocr_chars": ocr_chars,
                "first_raw_lines": raw[:30],
                "first_ocr_lines": ocr_lines[:30],
            }, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    raise ProcessingError(
        f"No text/lines extracted after pdfminer+OCR. "
        f"raw_count={len(raw)} raw_chars={raw_chars} ocr_count={len(ocr_lines)} ocr_chars={ocr_chars}"
    )


def assign_line_roles_fallback(lines: List[Dict]) -> List[Dict]:
    """
    Rule-based fallback for role assignment when models are missing or perform poorly
    """
    # Panel name patterns (case-insensitive)
    panel_patterns = re.compile(
        r'\b(CMP|COMPREHENSIVE METABOLIC PANEL|CBC|COMPLETE BLOOD COUNT|'
        r'LIPID PANEL|TSH|THYROID|BASIC METABOLIC PANEL|BMP|LIVER FUNCTION|'
        r'KIDNEY FUNCTION|ELECTROLYTES|CHEMISTRY)\b',
        re.IGNORECASE
    )
    
    # Unit patterns for test rows
    unit_patterns = re.compile(
        r'\b\d+\.?\d*\s*(mmol|mEq|IU|U/L|ng/mL|mg/dL|g/dL|mcg/dL|µg/L|pg/mL|'
        r'x10\^\d+|%|cells/µL|fL|pg|g/L|mL|L|U|ng|mg|mcg|µg|cells|K/µL|'
        r'/µL|/uL|per µL|per uL)\b',
        re.IGNORECASE
    )
    
    classified_lines = []
    
    for line_data in lines:
        text = line_data.get('text', '').strip()
        is_bold = line_data.get('is_bold', line_data.get('isBold', False))
        role = 'OTHER'  # Default
        confidence = 0.6  # Moderate confidence for rule-based
        
        if not text:
            role = 'EMPTY'
            confidence = 0.9
        
        # Check for section/panel headers
        elif (is_bold or text.isupper()) and panel_patterns.search(text):
            role = 'SECTION_PANEL'
            confidence = 0.8
        
        # Check for test rows (has number + unit pattern)
        elif unit_patterns.search(text):
            role = 'TEST_ROW'
            confidence = 0.7
        
        # Check for other common patterns
        elif 'page' in text.lower() or text.startswith(('Page', 'PAGE')):
            role = 'PAGE_HEADER'
            confidence = 0.8
        elif any(word in text.lower() for word in ['patient', 'name', 'dob', 'date of birth']):
            role = 'HEADER_PATIENT'
            confidence = 0.7
        elif any(word in text.lower() for word in ['specimen', 'collected', 'accession']):
            role = 'HEADER_SPECIMEN'
            confidence = 0.7
        
        classified_line = line_data.copy()
        classified_line['predicted_role'] = role
        classified_line['role_confidence'] = confidence
        classified_lines.append(classified_line)
    
    return classified_lines


def classify_roles(extraction_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Classify line roles using trained model with fallback support"""
    from collections import Counter
    global _roles_used_fallback_last, _roles_fallback_reason_last
    
    # Canonical roles allowed
    ALLOWED_ROLES = {"PAGE_HEADER", "PAGE_FOOTER", "HEADER_PATIENT", "HEADER_SPECIMEN",
                     "SECTION_PANEL", "TEST_ROW", "COMMENT", "SECTION_MISC", "JUNK"}
    
    # Initialize fallback tracking
    used_fallback = False
    fallback_reason = None
    
    # Check if we should force fallback
    if LAB_FORCE_FALLBACK:
        logger.info("🔄 LAB_FORCE_FALLBACK=1 - Using rule-based role classification")
        used_fallback = True
        fallback_reason = "LAB_FORCE_FALLBACK=1"
    
    # Check if model exists or is placeholder
    elif not _roles_model_ok:
        if _roles and _roles.is_placeholder:
            logger.info("🔄 Role model is placeholder - using rule-based fallback")
            fallback_reason = "roles_model_placeholder"
        else:
            logger.warning(f"⚠️  Role model not found - using fallback")
            fallback_reason = "roles_model_not_loaded"
        used_fallback = True
    
    # Build roles metadata for debug output
    roles_meta = {
        "loaded": _roles_model_ok,
        "fallback": used_fallback,
        "reason": fallback_reason if used_fallback else "model_loaded_successfully"
    }
    
    # Try to get model metadata
    try:
        if _roles and hasattr(_roles, 'meta') and _roles.meta:
            roles_meta["labels"] = _roles.meta.get('labels', [])
            roles_meta["embedding_model"] = _roles.meta.get('embedding_model', 'unknown')
        elif _roles and _roles.path:
            # Try to read from metadata.json
            metadata_path = Path(_roles.path) / "metadata.json"
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                    roles_meta["labels"] = metadata.get('labels', [])
                    roles_meta["embedding_model"] = metadata.get('embedding_model', 'unknown')
            else:
                roles_meta["labels"] = []
                roles_meta["embedding_model"] = "unknown"
        else:
            roles_meta["labels"] = []
            roles_meta["embedding_model"] = "unknown"
    except Exception as e:
        logger.debug(f"Could not read roles model metadata: {e}")
        roles_meta["labels"] = []
        roles_meta["embedding_model"] = "unknown"
    
    if used_fallback:
        # Use rule-based fallback
        rules_roles = tag_panels_rule_first(extraction_result['lines'])
        classified_lines = []
        probs_by_line = {}
        
        for i, line in enumerate(rules_roles):
            line_copy = line.copy()
            role = line_copy.get('predicted_role', 'JUNK')
            # Ensure canonical taxonomy
            if role not in ALLOWED_ROLES:
                role = 'JUNK'
            # Set canonical fields for composer
            line_copy['role'] = role
            line_copy['predicted_role'] = role  # Keep for debugging
            role_prob = line_copy.get('rule_confidence', 0.5)
            line_copy['role_prob'] = role_prob
            
            # Build probability distribution for fallback case
            probs_by_line[i] = {role: float(role_prob)}
            
            classified_lines.append(line_copy)
        
        _roles_used_fallback_last = True
        _roles_fallback_reason_last = fallback_reason
        return {
            "lines": classified_lines,
            "classifier_probabilities": probs_by_line,
            "metadata": extraction_result['metadata'],
            "roles_meta": roles_meta,
            "stats": {
                **extraction_result['stats'],
                "role_distribution": count_roles(classified_lines),
                "used_fallback": True,
                "fallback_reason": fallback_reason
            }
        }
    
    try:
        # Convert lines to Line objects for inference
        lines = []
        for line_data in extraction_result['lines']:
            lines.append(Line(
                text=line_data.get('text', ''),
                y_tertile=line_data.get('y_tertile', 0),
                is_bold=line_data.get('is_bold', False),
                is_header_hint=line_data.get('is_header_hint', False),
                font_size=line_data.get('font_size', 12.0),
                x_left=line_data.get('x_left', 0.0),
                width=line_data.get('width', 100.0),
                page=line_data.get('page', 1)
            ))
        
        # Use runtime inference model
        model_path = config.get('model_path', str(_roles.path))
        role_predictions = predict_line_roles(lines, model_path)
        
        # Get label order from model metadata if available
        labels = None
        try:
            if _roles and hasattr(_roles, 'meta') and _roles.meta:
                labels = _roles.meta.get('labels')
            elif _roles and _roles.path:
                # Try to read from metadata.json
                metadata_path = Path(_roles.path) / "metadata.json"
                if metadata_path.exists():
                    import json
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                        labels = metadata.get('labels')
        except Exception as e:
            logger.debug(f"Could not get label order from model metadata: {e}")
            labels = None
        
        # Process model predictions and set canonical fields
        classified_lines = []
        probabilities = []
        probs_by_line = {}
        
        for i, (original_line, prediction) in enumerate(zip(extraction_result['lines'], role_predictions)):
            classified_line = original_line.copy()
            
            # Map model output to canonical taxonomy
            pred_role = prediction.predicted_role
            
            # Normalize "OTHER" to "JUNK" for consistency
            if pred_role == 'OTHER':
                pred_role = 'JUNK'
            elif pred_role not in ALLOWED_ROLES:
                # Map unknown labels to JUNK or SECTION_MISC
                pred_role = 'SECTION_MISC' if pred_role.upper().find('SECTION') >= 0 else 'JUNK'
            
            # Set canonical fields for composer
            classified_line['role'] = pred_role  # Primary field consumed by composer
            classified_line['predicted_role'] = pred_role  # Keep for debugging
            classified_line['role_prob'] = float(prediction.confidence)  # Max probability
            
            # Keep detailed probabilities for debugging
            classified_line['role_confidence'] = prediction.confidence
            
            # Build probability distribution for this line
            line_no = i  # Use line index as line_number
            dist = None
            
            # Try full distribution first from prediction.probabilities
            if hasattr(prediction, 'probabilities') and prediction.probabilities:
                if isinstance(prediction.probabilities, dict):
                    # Already a dict {label: prob}
                    dist = prediction.probabilities
                elif isinstance(prediction.probabilities, (list, tuple)) and labels:
                    # Convert list to dict using label order
                    dist = {labels[j]: float(v) for j, v in enumerate(prediction.probabilities) if j < len(labels)}
                elif isinstance(prediction.probabilities, (list, tuple)):
                    # No labels available, create generic mapping
                    dist = {f"label_{j}": float(v) for j, v in enumerate(prediction.probabilities)}
            
            # Fallback to predicted_role + confidence
            if dist is None and pred_role and prediction.confidence:
                dist = {pred_role: float(prediction.confidence)}
            
            # Store probability distribution keyed by line number
            if dist is not None:
                probs_by_line[line_no] = dist
            
            classified_lines.append(classified_line)
            probabilities.append(prediction.probabilities)
        
        # Model inference succeeded - no fallback
        used_fallback = False
        fallback_reason = None
        
        # Update roles_meta for successful inference
        roles_meta["fallback"] = False
        roles_meta["reason"] = "model_loaded_successfully"
        
        # Store debug flags on the module for later introspection/logging
        _roles_used_fallback_last = used_fallback
        _roles_fallback_reason_last = fallback_reason
        
        # Run validation check
        validation_passed = _validate_role_predictions(classified_lines)
        
        return {
            "lines": classified_lines,
            "classifier_probabilities": probs_by_line,
            "metadata": extraction_result['metadata'],
            "roles_meta": roles_meta,
            "stats": {
                **extraction_result['stats'],
                "role_distribution": count_roles(classified_lines),
                "used_fallback": used_fallback,
                "fallback_reason": fallback_reason,
                "validation_passed": validation_passed
            }
        }
        
    except Exception as e:
        logger.warning(f"⚠️  Role classification model failed: {e} - using fallback")
        rules_roles = tag_panels_rule_first(extraction_result['lines'])
        # Map rules output to the standard taxonomy (no 'OTHER' leaks)
        classified_lines = []
        probs_by_line = {}
        
        for i, line in enumerate(rules_roles):
            line_copy = line.copy()
            role = line_copy.get('predicted_role', 'JUNK')
            # Normalize "OTHER" to "JUNK" for consistency
            if role == 'OTHER':
                role = 'JUNK'
            elif role not in ALLOWED_ROLES:
                role = 'JUNK'
            # Set canonical fields for composer
            line_copy['role'] = role
            line_copy['predicted_role'] = role
            role_prob = line_copy.get('rule_confidence', 0.5)
            line_copy['role_prob'] = role_prob
            
            # Build probability distribution for exception fallback case
            probs_by_line[i] = {role: float(role_prob)}
            
            classified_lines.append(line_copy)
        
        # Update roles_meta for exception fallback
        roles_meta["fallback"] = True
        roles_meta["reason"] = f"model_inference_failed: {str(e)}"
        
        _roles_used_fallback_last = True
        _roles_fallback_reason_last = str(e)
        return {
            "lines": classified_lines,
            "classifier_probabilities": probs_by_line,
            "metadata": extraction_result['metadata'],
            "roles_meta": roles_meta,
            "stats": {
                **extraction_result['stats'],
                "role_distribution": count_roles(classified_lines),
                "used_fallback": True,
                "fallback_reason": str(e)
            }
        }

def extract_patient_info_fallback(lines: List[Dict]) -> Dict[str, str]:
    """Simple fallback for patient info extraction"""
    patient_info = {}
    
    for line in lines:
        text = line.get('text', '').strip().lower()
        role = line.get('predicted_role', '')
        
        if role == 'HEADER_PATIENT':
            if 'name' in text:
                patient_info['name'] = text
            elif 'dob' in text or 'date of birth' in text:
                patient_info['dob'] = text
            elif 'id' in text or 'patient id' in text:
                patient_info['patient_id'] = text
    
    return patient_info

def extract_specimen_info_fallback(lines: List[Dict]) -> Dict[str, str]:
    """Simple fallback for specimen info extraction"""
    specimen_info = {}
    
    for line in lines:
        text = line.get('text', '').strip().lower()
        role = line.get('predicted_role', '')
        
        if role == 'HEADER_SPECIMEN':
            if 'specimen' in text:
                specimen_info['type'] = text
            elif 'collected' in text:
                specimen_info['collection_date'] = text
            elif 'accession' in text:
                specimen_info['accession'] = text
    
    return specimen_info

def extract_lab_info_fallback(lines: List[Dict]) -> Dict[str, str]:
    """Simple fallback for lab info extraction"""
    lab_info = {}
    
    for line in lines:
        text = line.get('text', '').strip().lower()
        role = line.get('predicted_role', '')
        
        if role in ['PAGE_HEADER', 'SECTION_PANEL']:
            if 'lab' in text or 'laboratory' in text:
                lab_info['lab_name'] = text
            elif 'report' in text:
                lab_info['report_type'] = text
    
    return lab_info

def classify_roles_fallback(lines: List[Dict]) -> List[Dict]:
    """Simple rule-based role classification fallback"""
    
    classified = []
    for line in lines:
        text = line.get('text', '').strip()
        role = 'OTHER'  # Default
        
        # Simple heuristics
        if not text:
            role = 'EMPTY'
        elif text.isupper() and len(text) > 10:
            role = 'SECTION_PANEL'
        elif any(word in text.lower() for word in ['test', 'result', 'normal', 'high', 'low']):
            role = 'TEST_ROW'
        elif any(word in text.lower() for word in ['patient', 'name', 'dob', 'id']):
            role = 'PATIENT_INFO'
        elif 'page' in text.lower() or text.startswith(('Page', 'PAGE')):
            role = 'PAGE_HEADER'
        
        classified.append({**line, 'role': role})
    
    return classified

def count_roles(lines: List[Dict]) -> Dict[str, int]:
    """Count distribution of roles"""
    counts = {}
    for line in lines:
        role = line.get('predicted_role', line.get('role', 'UNKNOWN'))
        counts[role] = counts.get(role, 0) + 1
    return counts

def _validate_role_predictions(lines: List[Dict]) -> bool:
    """
    Self-check to validate role predictions make sense.
    Returns True if validation passes.
    """
    import re
    
    # Check if panel headers are properly detected
    panel_patterns = [
        r'CBC.*[Ww]ith.*[Dd]ifferential',
        r'Comprehensive.*Metabolic.*Panel',
        r'CMP',
        r'Complete.*Blood.*Count'
    ]
    
    found_panel_header = False
    for line in lines:
        text = line.get('text', '').strip()
        role = line.get('role', line.get('predicted_role', ''))
        
        # Check if panel text was classified as SECTION_PANEL
        for pattern in panel_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                if role == 'SECTION_PANEL':
                    found_panel_header = True
                    logger.info(f"✅ Panel header validation passed: '{text}' -> {role}")
                else:
                    logger.warning(f"⚠️  Panel header validation failed: '{text}' -> {role} (expected SECTION_PANEL)")
                break
    
    return found_panel_header

def extract_headers(role_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract headers, specimen info, and patient data using enhanced meta extractors"""
    
    try:
        # NEW: Use enhanced meta extraction functions
        lines = role_result['lines']
        roles_data = role_result  # Pass full role result for context
        
        # Extract structured metadata using new extractors
        vendor_info = extract_vendor(lines, roles_data)
        patient_info = extract_patient(lines, roles_data)
        ordering_info = extract_ordering(lines, roles_data)
        specimen_info = extract_specimen(lines, roles_data)
        report_meta_info = extract_report_meta(lines, roles_data)
        
        # Maintain backward compatibility with legacy field names
        legacy_patient_info = {}
        if patient_info.get('first_name'):
            legacy_patient_info['name'] = f"{patient_info['first_name']} {patient_info.get('last_name', '')}"
        if patient_info.get('dob'):
            legacy_patient_info['dob'] = patient_info['dob']
        if patient_info.get('mrn'):
            legacy_patient_info['patient_id'] = patient_info['mrn']
        
        legacy_specimen_info = {}
        if specimen_info.get('type'):
            legacy_specimen_info['type'] = specimen_info['type']
        if specimen_info.get('collected_at'):
            legacy_specimen_info['collection_date'] = specimen_info['collected_at']
        if specimen_info.get('id'):
            legacy_specimen_info['accession'] = specimen_info['id']
        
        legacy_lab_info = {}
        if vendor_info.get('name'):
            legacy_lab_info['lab_name'] = vendor_info['name']
        elif report_meta_info.get('clinical_info'):
            legacy_lab_info['report_type'] = 'clinical'
        
        return {
            # Legacy format for backward compatibility
            "patient_info": legacy_patient_info,
            "specimen_info": legacy_specimen_info, 
            "lab_info": legacy_lab_info,
            # NEW: Structured extraction results
            "vendor_info": vendor_info,
            "patient_info_structured": patient_info,
            "ordering_info": ordering_info,
            "specimen_info_structured": specimen_info,
            "report_meta_info": report_meta_info,
            "extraction_stats": {
                "patient_fields": len([v for v in patient_info.values() if v]),
                "specimen_fields": len([v for v in specimen_info.values() if v]),
                "lab_fields": len([v for v in vendor_info.values() if v]),
                "ordering_fields": len([v for v in ordering_info.values() if v]),
                "meta_fields": len([v for v in report_meta_info.values() if v])
            }
        }
        
    except Exception as e:
        logger.warning(f"Header extraction failed: {str(e)}")
        return {
            "patient_info": {},
            "specimen_info": {},
            "lab_info": {},
            "vendor_info": {},
            "patient_info_structured": {},
            "ordering_info": {},
            "specimen_info_structured": {},
            "report_meta_info": {},
            "extraction_stats": {},
            "error": str(e)
        }

def process_test_rows(role_result: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Process test rows with token classification"""
    global _testrow_used_fallback_last
    
    # Build testrow metadata for debug output
    testrow_meta = {
        "fallback": False,
        "engine": "ml",
        "model_name": (_testrow_pipeline.name if globals().get("_testrow_pipeline") else None)
    }
    
    try:
        # Filter test rows
        test_rows = [line for line in role_result['lines'] if line.get('predicted_role') == 'TEST_ROW']
        
        # If a pipeline is present, use it
        if _ensure_testrow_pipeline():
            processed_rows: List[Dict[str, Any]] = []
            any_row_used_fallback = False
            for row in test_rows:
                text = (row.get('text') or '').strip()
                if not text:
                    processed_rows.append(row)
                    continue
                
                # Use the tag_testrow_line function; guard and reinit once if needed
                try:
                    result = tag_testrow_line(text)
                except NameError:
                    if _ensure_testrow_pipeline():
                        result = tag_testrow_line(text)
                    else:
                        raise
                
                # Check if meaningful fields were extracted
                fields = result.get("parsed_fields", {})
                meaningful = any(fields.get(k) for k in ("test_name", "result_value", "units", "reference_range", "flags"))
                
                if not meaningful or _testrow_used_fallback_last:
                    # Per-row fallback to existing rule-based splitter
                    any_row_used_fallback = True
                    processed = tag_testrows_rule_first([row])
                    processed_rows.extend(processed)
                    continue

                # Build processed row with token tags and parsed fields
                token_tags = []
                for tok in result.get("tokens", []):
                    token_tags.append({
                        'token': tok.get('token'),
                        'tag': tok.get('tag'),
                        'confidence': float(tok.get('confidence', 0.95)),
                        'start_pos': tok.get('start_pos'),
                        'end_pos': tok.get('end_pos'),
                    })

                pr = row.copy()
                # Map field names to match existing structure
                if fields.get("test_name"):
                    pr["test_name"] = fields.get("test_name")
                if fields.get("result_value"):
                    pr["result_value"] = fields.get("result_value")
                if fields.get("units"):
                    pr["units"] = fields.get("units")
                if fields.get("reference_range"):
                    pr["reference_range"] = fields.get("reference_range")
                if fields.get("flags"):
                    fl = fields.get("flags")
                    pr["flags"] = fl if isinstance(fl, list) else [fl]
                
                pr['token_tags'] = token_tags
                pr['parsed'] = True
                processed_rows.append(pr)

            _testrow_used_fallback_last = any_row_used_fallback
            testrow_meta["fallback"] = any_row_used_fallback
            return {
                "test_rows": processed_rows,
                "testrow_meta": testrow_meta,
                "stats": {
                    "total_test_rows": len(test_rows),
                    "successfully_parsed": len([r for r in processed_rows if r.get('parsed', False) or r.get('test_name')]),
                    "used_fallback": any_row_used_fallback,
                    "fallback_reason": "per-row" if any_row_used_fallback else None
                }
            }
        
        # No pipeline available — use rule-based fallback for all rows
        processed_rows = tag_testrows_rule_first(test_rows)
        _testrow_used_fallback_last = True
        testrow_meta["fallback"] = True
        return {
            "test_rows": processed_rows,
            "testrow_meta": testrow_meta,
            "stats": {
                "total_test_rows": len(test_rows),
                "successfully_parsed": len([r for r in processed_rows if r.get('test_name')]),
                "used_fallback": True,
                "fallback_reason": "no_crf_pipeline"
            }
        }
        
    except Exception as e:
        # Try reinitialize once on missing symbol and retry
        if isinstance(e, NameError):
            try:
                if _ensure_testrow_pipeline():
                    return process_test_rows(role_result, config)
            except Exception:
                pass
        logger.warning(f"Test row processing failed: {str(e)} - using fallback")
        test_rows = [line for line in role_result['lines'] if line.get('predicted_role') == 'TEST_ROW']
        processed_rows = tag_testrows_rule_first(test_rows)
        _testrow_used_fallback_last = True
        testrow_meta["fallback"] = True
        return {
            "test_rows": processed_rows,
            "testrow_meta": testrow_meta,
            "stats": {
                "total_test_rows": len(test_rows),
                "successfully_parsed": len([r for r in processed_rows if r.get('test_name')]),
                "used_fallback": True,
                "fallback_reason": str(e)
            }
        }

def parse_test_rows_simple(test_rows: List[Dict]) -> List[Dict]:
    """Simple test row parsing fallback"""
    import re
    
    parsed = []
    for row in test_rows:
        text = row.get('text', '').strip()
        parsed_row = {**row, 'parsed': False}
        
        # Simple regex patterns
        numeric_pattern = r'^(.+?)\s+([\d.,]+)\s*([a-zA-Z/%]+)?\s*(.*)$'
        text_pattern = r'^(.+?)\s+(POSITIVE|NEGATIVE|NORMAL|ABNORMAL|HIGH|LOW)\s*(.*)$'
        
        match = re.match(numeric_pattern, text)
        if not match:
            match = re.match(text_pattern, text, re.IGNORECASE)
        
        if match:
            parsed_row.update({
                'test_name': match.group(1).strip(),
                'result_value': match.group(2).strip(),
                'units': match.group(3).strip() if len(match.groups()) > 2 and match.group(3) else None,
                'reference_range': match.group(4).strip() if len(match.groups()) > 3 and match.group(4) else None,
                'parsed': True
            })
        
        parsed.append(parsed_row)
    
    return parsed

def compose_panels(testrow_result: Dict[str, Any], role_result: Dict[str, Any], config: Dict[str, Any], classifier_probabilities=None) -> Dict[str, Any]:
    """Compose panels with comprehensive scoring"""
    
    try:
        # Prepare lines data for composer
        lines_data = role_result['lines']
        
        # Initialize composer with scoring enabled
        composer_config = config.get('composer', {})
        scoring_config = config.get('scoring', {})
        
        composer = PanelComposer(
            page_break_lookahead=composer_config.get('page_break_lookahead', 8),
            min_continuity_score=composer_config.get('min_continuity_score', 0.3),
            cost_weight_switches=composer_config.get('cost_weight_switches', 2.0),
            cost_weight_coherence=composer_config.get('cost_weight_coherence', 1.0),
            enable_scoring=True,  # Always enable scoring
            scoring_config=scoring_config
        )
        
        # Compose panels
        result = composer.compose(lines_data, classifier_probabilities=classifier_probabilities)
        
        # Check if we need to synthesize auto-detected panel
        panel_count = len(result.panels)
        test_row_count = sum(len(line.get('text', '')) > 0 for line in lines_data 
                           if line.get('predicted_role') == 'TEST_ROW')
        section_panel_count = sum(1 for line in lines_data 
                                if line.get('predicted_role') == 'SECTION_PANEL')
        
        if panel_count == 0 and test_row_count >= 3 and section_panel_count == 0:
            logger.info(f"🔄 No panels detected but {test_row_count} TEST_ROWs found - synthesizing auto-detected panel")
            
            # Create synthetic panel with all test rows
            from services.worker.composer.schemas import Panel, TestRow
            import uuid
            
            auto_panel = Panel(
                id=str(uuid.uuid4())[:8],
                name="Auto-detected Panel",
                started_at_page=1,
                started_at_line=0,
                continuity_score=0.5,
                open=False,
                test_rows=[]
            )
            
            # Add test rows in reading order
            for i, line_data in enumerate(lines_data):
                if line_data.get('predicted_role') == 'TEST_ROW':
                    test_row = TestRow(
                        text=line_data.get('text', ''),
                        page=line_data.get('page', 1),
                        line_number=i,
                        y_norm=line_data.get('yNorm', line_data.get('y_norm', 0.0))
                    )
                    auto_panel.add_test_row(test_row)
            
            result.panels = [auto_panel]
            logger.info(f"✅ Created auto-detected panel with {len(auto_panel.test_rows)} test rows")
        
        # Convert to JSON format
        ehr_data = json.loads(result.to_ehr_json())
        
        # Add fallback information to document_info
        document_info = ehr_data["document_info"]
        
        # Add processing stats with fallback information
        if "processing_stats" not in document_info:
            document_info["processing_stats"] = {}
        
        document_info["processing_stats"]["roles_used_fallback"] = bool(_roles_used_fallback_last)
        document_info["processing_stats"]["testrow_used_fallback"] = bool(_testrow_used_fallback_last)
        document_info["processing_stats"]["models_available"] = {
            "roles_model_ok": _roles_model_ok,
            "testrow_model_ok": _testrow_model_ok
        }
        
        # Add review reasons if fallbacks were used
        review_reasons = list(result.review_reasons or [])
        if _roles_used_fallback_last:
            review_reasons.append("Role classification used rule-based fallback")
        if _testrow_used_fallback_last:
            review_reasons.append("Test row parsing used rule-based fallback")
        
        return {
            "success": True,
            "document_info": document_info,
            "lab_panels": ehr_data["lab_panels"],
            "summary": result.get_summary(),
            "testrow_meta": testrow_result.get("testrow_meta", {"loaded": False, "fallback": True, "reason": "no_testrow_data"}),
            "quality_metrics": {
                "document_score": result.document_score,
                "needs_review": result.needs_review or bool(_roles_used_fallback_last or _testrow_used_fallback_last),
                "review_reasons": review_reasons,
                "confidence_distribution": result.confidence_distribution
            }
        }
        
    except Exception as e:
        raise ProcessingError(f"Panel composition failed: {str(e)}")

def build_diagnostic_report(composition_result: Dict[str, Any], header_result: Dict[str, Any]) -> DiagnosticReport:
    """Build EHR-compatible DiagnosticReport from processing results"""
    # NEW: Convert legacy data structures to EHR schema
    
    # Extract patient info - prefer structured data over legacy
    patient_structured = header_result.get("patient_info_structured", {})
    if patient_structured and any(patient_structured.values()):
        # Use enhanced extraction results
        patient = Patient(**{k: v for k, v in patient_structured.items() if v is not None})
    else:
        # Fall back to legacy format
        patient_info = header_result.get("patient_info", {})
        patient = Patient(
            last_name=patient_info.get("last_name"),
            first_name=patient_info.get("first_name"),
            middle=patient_info.get("middle"),
            dob=patient_info.get("dob"),
            sex=patient_info.get("sex"),
            mrn=patient_info.get("patient_id") or patient_info.get("mrn"),
            phone=patient_info.get("phone")
        ) if patient_info else None
    
    # Extract specimen info - prefer structured data
    specimen_structured = header_result.get("specimen_info_structured", {})
    if specimen_structured and any(specimen_structured.values()):
        specimen = Specimen(**{k: v for k, v in specimen_structured.items() if v is not None})
    else:
        # Fall back to legacy format
        specimen_info = header_result.get("specimen_info", {})
        specimen = Specimen(
            id=specimen_info.get("accession"),
            type=specimen_info.get("type"),
            collected_at=specimen_info.get("collection_date"),
            received_at=specimen_info.get("received_date"),
            reported_at=specimen_info.get("report_date")
        ) if specimen_info else None
    
    # Extract vendor info - prefer structured data
    vendor_structured = header_result.get("vendor_info", {})
    if vendor_structured and any(vendor_structured.values()):
        # Convert address dict to Address object if needed
        if vendor_structured.get('address') and isinstance(vendor_structured['address'], dict):
            vendor_structured = vendor_structured.copy()
            vendor_structured['address'] = Address(**vendor_structured['address'])
        vendor = Vendor(**{k: v for k, v in vendor_structured.items() if v is not None})
    else:
        # Fall back to document_info and lab_info
        doc_info = composition_result.get("document_info", {})
        lab_info = header_result.get("lab_info", {})
        vendor = Vendor(
            name=doc_info.get("lab_name") or lab_info.get("lab_name"),
            account_number=doc_info.get("account_number")
        ) if (doc_info or lab_info) else None
    
    # Extract performing lab info
    lab_info = header_result.get("lab_info", {})
    performing_lab = PerformingLab(
        name=lab_info.get("lab_name"),
        clia=lab_info.get("clia"),
        director=lab_info.get("director")
    ) if lab_info else None
    
    # Extract ordering provider info
    ordering_structured = header_result.get("ordering_info", {})
    ordering = None
    if ordering_structured and any(ordering_structured.values()):
        # Convert nested location dict to OrderingLocation object if needed
        if ordering_structured.get('location') and isinstance(ordering_structured['location'], dict):
            location_data = ordering_structured['location'].copy()
            if location_data.get('address') and isinstance(location_data['address'], dict):
                location_data['address'] = Address(**location_data['address'])
            ordering_structured = ordering_structured.copy()
            ordering_structured['location'] = OrderingLocation(**location_data)
        ordering = OrderingProvider(**{k: v for k, v in ordering_structured.items() if v is not None})
    
    # Extract report info
    report_info = ReportInfo(
        id=doc_info.get("document_id"),
        page=doc_info.get("page"),
        page_count=doc_info.get("page_count")
    ) if doc_info else None
    
    # Convert lab panels to schema format
    lab_panels = composition_result.get("lab_panels", [])
    panels = []
    
    for panel_data in lab_panels:
        # Convert test rows
        test_rows = []
        for test_data in panel_data.get("test_rows", []):
            # Extract reference range - normalize string/dict input
            _rr = _coerce_ref_range(test_data.get("reference_range"))
            ref_range = None
            if _rr["text"] or _rr["low"] or _rr["high"]:
                ref_range = ReferenceRange(
                    text=_rr["text"],
                    low=_rr["low"],
                    high=_rr["high"]
                )
            
            # Extract test codes
            test_code = None
            if test_data.get("codes"):
                test_code = TestCode(
                    loinc=test_data["codes"].get("loinc"),
                    cpt=test_data["codes"].get("cpt")
                )
            
            # Normalize flag
            flag = _coerce_flag(test_data.get("flag") or test_data.get("flags"))
            
            test_row = TestRow(
                name=test_data.get("test_name"),
                value=test_data.get("result_value"),
                unit=test_data.get("unit"),
                reference_range=ref_range,
                flag=flag,
                code=test_code,
                methodology=test_data.get("methodology"),
                comments=test_data.get("comments"),
                observed_at=test_data.get("observation_date")
            )
            test_rows.append(test_row)
        
        panel = Panel(
            name=panel_data.get("panel_name"),
            code=panel_data.get("panel_code"),
            comments=panel_data.get("comments"),
            tests=test_rows
        )
        panels.append(panel)
    
    # Extract report metadata
    report_meta_structured = header_result.get("report_meta_info", {})
    report_meta = None
    if report_meta_structured and any(report_meta_structured.values()):
        report_meta = ReportMeta(**{k: v for k, v in report_meta_structured.items() if v is not None})
    
    # Build complete diagnostic report
    diagnostic_report = DiagnosticReport(
        vendor=vendor,
        report=report_info,
        performing_lab=performing_lab,
        patient=patient,
        ordering=ordering,
        specimen=specimen,
        report_meta=report_meta,
        panels=panels
    )
    
    return diagnostic_report

def write_output(job_id: str, composition_result: Dict[str, Any], header_result: Dict[str, Any]) -> Path:
    """Write final JSON output"""
    
    output_path = OUTBOX_DIR / f"{job_id}.json"
    
    # NEW: Build EHR-compatible diagnostic report
    diagnostic_report = build_diagnostic_report(composition_result, header_result)
    
    # Combine all results (keep legacy format for backward compatibility)
    final_output = {
        "document_info": {
            **composition_result["document_info"],
            "patient_info": header_result.get("patient_info", {}),
            "specimen_info": header_result.get("specimen_info", {}),
            "lab_info": header_result.get("lab_info", {})
        },
        "lab_panels": composition_result["lab_panels"],
        "processing_summary": {
            "quality_metrics": composition_result["quality_metrics"],
            "panel_summary": composition_result["summary"]
        },
        # NEW: Add EHR-compatible structured payload
        "ehr_payload": diagnostic_report.to_dict()
    }
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, indent=2, ensure_ascii=False)
    
    return output_path

def cleanup_temp_files(pdf_path: Path):
    """Clean up temporary files"""
    try:
        if pdf_path.parent == TEMP_DIR and pdf_path.exists():
            pdf_path.unlink()
    except Exception as e:
        logger.warning(f"Failed to cleanup temp file {pdf_path}: {str(e)}")

# Helper tasks for testing
@app.task(name='worker.test_task')
def test_task(message: str):
    """Simple test task"""
    return {"message": f"Test completed: {message}", "timestamp": datetime.now().isoformat()}

@app.task(name='worker.health_check')
def health_check():
    """Worker health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "worker_id": os.getpid()
    }

def _map_merged_roles_to_original(original_lines: List[Dict], merged_role_result: Dict, merged_lines: List[Dict]) -> Dict:
    """
    Map role predictions from merged lines back to original lines.
    
    Args:
        original_lines: Original extraction lines
        merged_role_result: Role classification result on merged lines
        merged_lines: The merged lines used for classification
        
    Returns:
        Role result with original line structure
    """
    from collections import Counter
    # Create a mapping from original line indexes to merged line indexes
    original_to_merged = {}
    
    for merged_idx, merged_line in enumerate(merged_lines):
        # Each merged line has a 'cells' array with original line data
        cells = merged_line.get('cells', [])
        for cell in cells:
            # Find the original line index for this cell
            for orig_idx, orig_line in enumerate(original_lines):
                if (orig_line.get('text') == cell.get('text') and 
                    orig_line.get('page') == cell.get('page') and
                    abs(orig_line.get('xLeft', 0) - cell.get('xLeft', 0)) < 0.1):
                    original_to_merged[orig_idx] = merged_idx
                    break
    
    # Create result with original line structure but merged roles
    classified_original_lines = []
    for orig_idx, orig_line in enumerate(original_lines):
        classified_line = orig_line.copy()
        
        # Find the corresponding merged line
        merged_idx = original_to_merged.get(orig_idx)
        if merged_idx is not None and merged_idx < len(merged_role_result['lines']):
            merged_line = merged_role_result['lines'][merged_idx]
            # Copy role information from merged line
            classified_line['role'] = merged_line.get('role', 'JUNK')
            classified_line['predicted_role'] = merged_line.get('predicted_role', 'JUNK')
            classified_line['role_prob'] = merged_line.get('role_prob', 0.5)
        else:
            # Default role for lines that couldn't be mapped
            classified_line['role'] = 'JUNK'
            classified_line['predicted_role'] = 'JUNK'
            classified_line['role_prob'] = 0.1
        
        classified_original_lines.append(classified_line)
    
    # Create result structure compatible with downstream processing
    result = {
        "lines": classified_original_lines,
        "classifier_probabilities": merged_role_result.get('classifier_probabilities', []),
        "metadata": merged_role_result.get('metadata', {}),
        "stats": {
            **merged_role_result.get('stats', {}),
            "role_distribution": dict(Counter(
                line.get('predicted_role', 'UNKNOWN') for line in classified_original_lines
            )),
            "original_line_count": len(original_lines),
            "merged_line_count": len(merged_lines)
        }
    }
    
    return result


## Removed duplicate tag_testrow_line that depended on runtime.testrow_infer

def print_model_status():
    """Print model status for CLI"""
    print(f"roles_model_ok: {_roles_model_ok}")
    print(f"testrow_model_ok: {_testrow_model_ok}")
    print(f"roles_used_fallback_last: {_roles_used_fallback_last}")
    print(f"testrow_used_fallback_last: {_testrow_used_fallback_last}")
    print(f"roles_path: {_roles.path}")
    print(f"testrow_path: {_testrow.path}")

# Eager load on import
try:
    load_testrow_model()
except Exception as e:
    logging.getLogger(__name__).warning("TestRow eager load failed: %s", e)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--print-model-status":
        print_model_status()
    elif len(sys.argv) > 1 and sys.argv[1] == "--test-helpers":
        # Smoke tests for helpers
        assert _coerce_ref_range("70-99") == {"text":"70-99","low":70.0,"high":99.0}
        assert _coerce_ref_range("70-99 01")["text"] == "70-99 01"
        assert _coerce_ref_range({"text":"10-24","low":"10","high":"24"}) == {"text":"10-24","low":10.0,"high":24.0}
        assert _coerce_flag(None) is None
        assert _coerce_flag("H") == "H"
        assert _coerce_flag(["L"]) == "L"
        print("helpers OK")
    else:
        print("Usage: python -m services.worker.tasks --print-model-status | --test-helpers")
