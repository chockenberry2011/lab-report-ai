import os
import json
import uuid
import tempfile
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Union
import logging

import uvicorn
import redis
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
from celery import Celery
import sys
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

# Health routes (package import)
from api.routes import healthz as healthz_routes

# Setup logging
logger = logging.getLogger("api")
logger.setLevel(logging.DEBUG)

# Models
class JobSubmission(BaseModel):
    pdf_url: Optional[HttpUrl] = None
    config: Optional[Dict[str, Any]] = None

class JobResponse(BaseModel):
    job_id: str
    status: str
    created_at: str
    message: str

class JobStatus(BaseModel):
    job_id: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: Dict[str, Any] = {}
    result_url: Optional[str] = None
    error: Optional[str] = None

class JobRegistryEntry(BaseModel):
    id: str
    filename: Optional[str] = None
    created_at: str
    updated_at: str
    status: str  # queued, processing, done, failed
    result_path: Optional[str] = None
    error: Optional[str] = None

class JobListResponse(BaseModel):
    jobs: List[JobRegistryEntry]
    total: int
    page: int
    per_page: int
    has_next: bool

class HealthResponse(BaseModel):
    ok: bool

class CorrectionsPayload(BaseModel):
    corrections: List[Dict[str, Any]]

class TrainingPayload(BaseModel):
    include_manual_corrections: Optional[bool] = False
    annotations: Optional[List[Dict[str, Any]]] = []

# If this import is needed here, use package path rooted at api
from api.utils.ids import normalize_result_id

def _load_corrections(base_id: str) -> Dict[str, Any]:
    """Load corrections from JSON file"""
    corrections_file = DATA_DIR / f"{base_id}.corrections.json"
    if not corrections_file.exists():
        return {"corrections": []}
    
    try:
        return json.loads(corrections_file.read_text(encoding="utf-8"))
    except Exception:
        return {"corrections": []}

def _save_corrections(base_id: str, corrections_data: Dict[str, Any]):
    """Save corrections to JSON file"""
    corrections_file = DATA_DIR / f"{base_id}.corrections.json"
    corrections_file.write_text(
        json.dumps(corrections_data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def decode_job_registry_entry(data: Union[str, bytes, dict]) -> JobRegistryEntry:
    """Convert arbitrary payload (bytes|str|dict) into a JobRegistryEntry with robust type handling."""
    if isinstance(data, (bytes, bytearray)):
        decoded_data = json.loads(data.decode("utf-8"))
    elif isinstance(data, str):
        decoded_data = json.loads(data)
    elif isinstance(data, dict):
        decoded_data = data
    else:
        raise TypeError(f"Unsupported job registry payload type: {type(data)!r}")
    return JobRegistryEntry(**decoded_data)

# Import smoke test before creating the app
try:
    import api._import_smoke  # type: ignore  # noqa: F401
except Exception as e:  # pragma: no cover
    logger = logging.getLogger("api")
    logger.exception("import_smoke_failed: %s", e)
    raise

# FastAPI app
app = FastAPI(
    title="Lab AI Processing API", 
    version="1.0.0",
    description="""API for processing lab reports with ML-based data extraction and quality scoring.

## Features
- Submit lab reports for processing via file upload or URL
- Track job status with comprehensive job registry
- List and filter jobs with pagination
- Download processed results
- Health monitoring

## Job Registry
Jobs are tracked with the following statuses:
- `queued`: Job is waiting to be processed
- `processing`: Job is currently being processed  
- `done`: Job completed successfully
- `failed`: Job failed or was cancelled

## CORS
Enabled for localhost development ports (3000, 3001, 5173, 8000, 8080).
    """,
    openapi_tags=[
        {"name": "jobs", "description": "Job management and processing"},
        {"name": "results", "description": "Result retrieval"},
        {"name": "system", "description": "Health and system information"}
    ]
)

# Correlation id middleware
@app.middleware("http")
async def attach_req_id(request: Request, call_next):
    req_id = request.headers.get("X-Req-Id") or str(uuid.uuid4())
    request.state.req_id = req_id
    response = await call_next(request)
    try:
        response.headers["X-Req-Id"] = req_id
    except Exception:
        pass
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    raw = await request.body()
    logger.error("422 validation error on %s | headers=%s | body=%s | errors=%s",
                 str(request.url), dict(request.headers), raw.decode("utf-8", "ignore"),
                 exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

# Meta endpoint for debugging
@app.get("/__meta")
def meta():
    return {
        "cwd": os.getcwd(),
        "sys_path_head": sys.path[:5],
        "env_subset": {k: v for k, v in os.environ.items() if k in ("PYTHONPATH","MODEL_ROLES_DIR","MODEL_TESTROW_DIR","REDIS_URL")}
    }

# Include routers via absolute package imports
from api import results as results_routes
from api import jobs as jobs_routes
from api import corrections_api as corrections_routes
from api import admin_api as admin_routes
app.include_router(results_routes.router)
app.include_router(jobs_routes.router)
app.include_router(corrections_routes.router)
app.include_router(admin_routes.router)

# Include healthz router (using robust import from above)
app.include_router(healthz_routes.router, prefix="/healthz", tags=["health"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Common React dev port
        "http://localhost:3001",
        "http://localhost:5173",  # Common Vite dev port
        "http://localhost:8080",
        "http://localhost:8000",
        "*"  # Allow all origins for now (can be tightened later)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CELERY_BROKER = os.getenv("CELERY_BROKER", REDIS_URL)
CELERY_BACKEND = os.getenv("CELERY_BACKEND", REDIS_URL)
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
OUTBOX_DIR = DATA_DIR / "outbox"
INBOX_DIR = DATA_DIR / "inbox"

# Ensure directories exist
OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
INBOX_DIR.mkdir(parents=True, exist_ok=True)

# Redis connection for job tracking (decode responses to str consistently)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

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

@app.on_event("startup")
async def rebuild_indices_if_missing():
    """Rebuild job indices on startup if they're missing"""
    need = not (redis_client.exists("jobs:index") and redis_client.exists("jobs:recent") and redis_client.exists("jobs:by_updated_at"))
    if not need:
        return
    
    print("🔄 Rebuilding missing job indices...")
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
    print(f"✅ Rebuilt job indices for {len(ids)} jobs")
    
    # Print routes at startup
    paths = []
    for r in app.routes:
        try:
            paths.append(getattr(r, "path"))
        except Exception:
            pass
    print("Mounted routes:", paths)

# Celery connection for job queuing
celery_app = Celery('lab_ai_api', broker=CELERY_BROKER, backend=CELERY_BACKEND)

# JobRegistry for tracking jobs with Redis or file fallback
class JobRegistry:
    def __init__(self, redis_client=None, fallback_file=None):
        self.redis_client = redis_client
        self.fallback_file = Path(fallback_file or DATA_DIR / "jobs.json")
        self.use_redis = redis_client is not None
        
        # Ensure fallback file exists
        if not self.use_redis and not self.fallback_file.exists():
            self.fallback_file.write_text(json.dumps({}))
    
    def _load_from_file(self) -> Dict[str, Dict[str, Any]]:
        """Load jobs from local file"""
        try:
            with open(self.fallback_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save_to_file(self, jobs: Dict[str, Dict[str, Any]]):
        """Save jobs to local file"""
        with open(self.fallback_file, 'w') as f:
            json.dump(jobs, f, indent=2)
    
    def register_job(self, job_id: str, filename: str = None, status: str = "queued"):
        """Register a new job"""
        now = datetime.now(timezone.utc).isoformat()
        job_entry = {
            "id": job_id,
            "filename": filename,
            "created_at": now,
            "updated_at": now,
            "status": status,
            "result_path": None,
            "error": None
        }
        
        if self.use_redis:
            try:
                # Store in Redis registry
                self.redis_client.hset(
                    f"registry:job:{job_id}",
                    mapping={k: str(v) if v is not None else "" for k, v in job_entry.items()}
                )
                # Add to sorted set for quick listing by creation time
                self.redis_client.zadd("registry:jobs:by_created", {job_id: now})
                return
            except Exception:
                # Fall back to file if Redis fails
                pass
        
        # Fallback to file
        jobs = self._load_from_file()
        jobs[job_id] = job_entry
        self._save_to_file(jobs)
    
    def update_job(self, job_id: str, **updates):
        """Update job status and other fields"""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        if self.use_redis:
            try:
                # Update in Redis
                self.redis_client.hset(
                    f"registry:job:{job_id}",
                    mapping={k: str(v) if v is not None else "" for k, v in updates.items()}
                )
                return
            except Exception:
                pass
        
        # Fallback to file
        jobs = self._load_from_file()
        if job_id in jobs:
            jobs[job_id].update(updates)
            self._save_to_file(jobs)
    
    def get_job(self, job_id: str) -> Optional[JobRegistryEntry]:
        """Get a single job by ID"""
        if self.use_redis:
            try:
                job_data = self.redis_client.hgetall(f"registry:job:{job_id}")
                if job_data:
                    # Values already decoded to str via decode_responses=True
                    decoded_data = {k: (v or None) for k, v in job_data.items()}
                    return decode_job_registry_entry(decoded_data)
            except Exception:
                pass
            
            # Fallback to file
            jobs = self._load_from_file()
            if job_id in jobs:
                return decode_job_registry_entry(jobs[job_id])
            return None
    
    def list_jobs(self, page: int = 1, per_page: int = 50, status: str = None, query: str = None) -> JobListResponse:
        """List jobs with pagination and filtering"""
        if self.use_redis:
            try:
                return self._list_jobs_redis(page, per_page, status, query)
            except Exception:
                pass
        
        # Fallback to file
        return self._list_jobs_file(page, per_page, status, query)
    
    def _list_jobs_redis(self, page: int, per_page: int, status: str, query: str) -> JobListResponse:
        """List jobs from Redis"""
        # Get all job IDs sorted by creation time (newest first)
        job_ids = self.redis_client.zrevrange("registry:jobs:by_created", 0, -1)
        
        # Filter jobs
        filtered_jobs = []
        for job_id in job_ids:
            job_data = self.redis_client.hgetall(f"registry:job:{job_id}")
            if not job_data:
                continue
            
            # Already decoded to str
            decoded_data = {k: (v or None) for k, v in job_data.items()}
            
            # Apply filters
            if status and decoded_data.get('status') != status:
                continue
            if query:
                query_lower = query.lower()
                if not (
                    query_lower in job_id.lower() or
                    (decoded_data.get('filename') and query_lower in decoded_data.get('filename').lower())
                ):
                    continue
            
            filtered_jobs.append(decode_job_registry_entry(decoded_data))
        
        # Pagination
        total = len(filtered_jobs)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_jobs = filtered_jobs[start_idx:end_idx]
        
        return JobListResponse(
            jobs=paginated_jobs,
            total=total,
            page=page,
            per_page=per_page,
            has_next=end_idx < total
        )
    
    def _list_jobs_file(self, page: int, per_page: int, status: str, query: str) -> JobListResponse:
        """List jobs from file"""
        jobs = self._load_from_file()
        
        # Convert to list and sort by created_at (newest first)
        job_list = list(jobs.values())
        job_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Apply filters
        if status:
            job_list = [j for j in job_list if j.get('status') == status]
        if query:
            query_lower = query.lower()
            job_list = [
                j for j in job_list
                if query_lower in j.get('id', '').lower() or
                   (j.get('filename') and query_lower in j.get('filename', '').lower())
            ]
        
        # Pagination
        total = len(job_list)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_jobs = job_list[start_idx:end_idx]
        
        return JobListResponse(
            jobs=[decode_job_registry_entry(job) for job in paginated_jobs],
            total=total,
            page=page,
            per_page=per_page,
            has_next=end_idx < total
        )

# Initialize job registry
try:
    job_registry = JobRegistry(redis_client=redis_client)
except Exception:
    job_registry = JobRegistry(redis_client=None)

# Helper function to update job status in both systems
def update_job_status(job_id: str, status: str, **extra_fields):
    """Update job status in both old Redis system and new JobRegistry"""
    # Add updated_at timestamp if not provided
    if "updated_at" not in extra_fields:
        extra_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Update old Redis system
    redis_client.hset(f"job:{job_id}", "status", status)
    if extra_fields:
        redis_client.hset(f"job:{job_id}", mapping={
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
            for k, v in extra_fields.items()
        })
    
    # Update JobRegistry (map statuses to registry format)
    registry_status = status
    if status == "completed":
        registry_status = "done"
    elif status == "processing":
        registry_status = "processing"
    elif status == "failed":
        registry_status = "failed"
    elif status == "cancelled":
        registry_status = "failed"  # Treat cancelled as failed in registry
    
    updates = {"status": registry_status}
    updates.update(extra_fields)
    job_registry.update_job(job_id, **updates)
    
    # Update job indices to keep them current
    update_job_indices(redis_client, job_id, registry_status, extra_fields.get("updated_at"))

@app.get("/", response_model=dict, tags=["system"])
async def root():
    """API root endpoint"""
    return {
        "message": "Lab AI Processing API",
        "version": "1.0.0",
        "endpoints": {
            "submit_job": "POST /jobs - Submit processing job",
            "list_jobs": "GET /jobs - List jobs with pagination and filtering",
            "get_job": "GET /jobs/{job_id} - Get job status and details", 
            "get_results": "GET /results/{job_id} - Download results",
            "save_corrections": "POST /results/{job_id}/corrections - Save manual corrections",
            "health": "GET /health - Health check",
            "debug_routes": "GET /debug/routes - List all mounted routes"
        }
    }


@app.get("/debug/routes", tags=["system"])
async def debug_routes():
    """Debug endpoint to list all mounted routes"""
    paths = []
    for r in app.routes:
        try:
            if hasattr(r, 'path'):
                paths.append(r.path)
            elif hasattr(r, 'path_regex'):
                paths.append(str(r.path_regex.pattern))
        except Exception:
            pass
    return {"routes": sorted(paths)}

@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    """Health check endpoint"""
    return HealthResponse(ok=True)

@app.post("/jobs", response_model=JobResponse, tags=["jobs"])
async def submit_job(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    pdf_url: Optional[str] = Form(None),
    config: Optional[str] = Form("{}")
):
    """
    Submit a lab report processing job
    
    Accepts either:
    - Multipart file upload (PDF)
    - URL to PDF document
    
    Returns job_id for tracking
    """
    if not file and not pdf_url:
        raise HTTPException(
            status_code=400, 
            detail="Either file upload or pdf_url must be provided"
        )
    
    if file and pdf_url:
        raise HTTPException(
            status_code=400,
            detail="Provide either file upload or pdf_url, not both"
        )
    
    # Generate job ID
    job_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    try:
        # Parse config
        job_config = json.loads(config) if config else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in config parameter")
    
    # Register job in JobRegistry
    filename = None
    if file:
        filename = file.filename
    
    job_registry.register_job(job_id, filename=filename, status="queued")
    
    # Store job metadata in Redis (existing behavior)
    job_data = {
        "job_id": job_id,
        "status": "queued",
        "created_at": created_at,
        "config": job_config,
        "progress": {}
    }
    
    if file:
        # Handle file upload
        job_data["source"] = "upload"
        job_data["filename"] = file.filename
        job_data["content_type"] = file.content_type
        
        # Save uploaded file
        input_file = INBOX_DIR / f"{job_id}.pdf"
        try:
            content = await file.read()
            with open(input_file, "wb") as f:
                f.write(content)
            job_data["input_file"] = str(input_file)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")
            
    elif pdf_url:
        # Handle URL
        job_data["source"] = "url"
        job_data["pdf_url"] = pdf_url
    
    # Store in Redis
    redis_client.hset(f"job:{job_id}", mapping={
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
        for k, v in job_data.items()
    })
    
    # Queue the job
    celery_task = celery_app.send_task(
        'worker.process_lab_report',
        args=[job_id],
        queue='lab_processing'
    )
    
    # Store Celery task ID
    redis_client.hset(f"job:{job_id}", "celery_task_id", celery_task.id)
    
    return JobResponse(
        job_id=job_id,
        status="queued",
        created_at=created_at,
        message="Job queued for processing"
    )

@app.get("/jobs/{job_id}", response_model=JobStatus, tags=["jobs"])
async def get_job_status(job_id: str):
    """Get job status and progress"""
    
    # Check if job exists
    job_data = redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Decode Redis data (already strings)
    job_info = {}
    for key, value in job_data.items():
        # Try to parse JSON for complex fields
        if key in ['config', 'progress', 'result']:
            try:
                job_info[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                job_info[key] = value
        else:
            job_info[key] = value
    
    # Check for result file and update registry
    result_url = None
    if job_info.get('status') == 'completed':
        result_file = OUTBOX_DIR / f"{job_id}.json"
        if result_file.exists():
            result_url = f"/results/{job_id}"
            # Update registry with result path if not already set
            registry_entry = job_registry.get_job(job_id)
            if registry_entry and not registry_entry.result_path:
                job_registry.update_job(job_id, result_path=str(result_file), status="done")
    
    return JobStatus(
        job_id=job_id,
        status=job_info.get('status', 'unknown'),
        created_at=job_info.get('created_at', ''),
        started_at=job_info.get('started_at'),
        completed_at=job_info.get('completed_at'),
        progress=job_info.get('progress', {}),
        result_url=result_url,
        error=job_info.get('error')
    )

@app.get("/jobs", response_model=JobListResponse, tags=["jobs"])
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(50, ge=1, le=1000, description="Jobs per page"),
    status: Optional[str] = Query(None, description="Filter by status: queued, processing, done, failed"),
    q: Optional[str] = Query(None, description="Search query (matches job ID and filename)")
):
    """
    List jobs with pagination and filtering
    
    Supports:
    - Pagination with page and per_page parameters
    - Status filtering: ?status=queued|processing|done|failed
    - Text search: ?q=searchterm (searches job ID and filename)
    """
    return job_registry.list_jobs(page=page, per_page=per_page, status=status, query=q)

@app.get("/results/{job_id}", tags=["results"])
async def get_job_result(job_id: str):
    """Download job result JSON"""
    
    # Check if job exists and is completed
    job_status = redis_client.hget(f"job:{job_id}", "status")
    if not job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job_status != 'completed':
        raise HTTPException(status_code=400, detail=f"Job not completed (status: {job_status})")
    
    # Check for result file
    result_file = OUTBOX_DIR / f"{job_id}.json"
    if not result_file.exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return FileResponse(
        path=result_file,
        media_type='application/json',
        filename=f"lab_results_{job_id}.json"
    )

@app.get("/jobs/{job_id}/logs", tags=["jobs"])
async def get_job_logs(job_id: str):
    """Get job processing logs"""
    
    # Check if job exists
    if not redis_client.exists(f"job:{job_id}"):
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get logs from Redis
    logs = redis_client.lrange(f"job:{job_id}:logs", 0, -1)
    log_entries = [json.loads(log) for log in logs]
    
    return {"job_id": job_id, "logs": log_entries}

@app.delete("/jobs/{job_id}", tags=["jobs"])
async def cancel_job(job_id: str):
    """Cancel a queued or running job"""
    
    job_data = redis_client.hgetall(f"job:{job_id}")
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get current status
    current_status = job_data.get('status', '')
    
    if current_status == 'completed':
        raise HTTPException(status_code=400, detail="Cannot cancel completed job")
    
    if current_status == 'cancelled':
        return {"message": "Job already cancelled"}
    
    # Cancel Celery task if exists
    celery_task_id = job_data.get('celery_task_id')
    if celery_task_id:
        celery_app.control.revoke(celery_task_id, terminate=True)
    
    # Update status
    update_job_status(job_id, "cancelled", cancelled_at=datetime.now(timezone.utc).isoformat())
    
    return {"message": "Job cancelled successfully"}

@app.get("/stats", tags=["system"])
async def get_system_stats():
    """Get system statistics"""
    
    # Get all job keys
    job_keys = redis_client.keys("job:*")
    # Robust handling of bytes/str keys and filtering out ':logs' entries
    keys = [k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else k for k in job_keys]
    processed_keys = [k for k in keys if not k.endswith(":logs")]
    
    stats = {
        "total_jobs": len(processed_keys),
        "status_counts": {
            "queued": 0,
            "processing": 0, 
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        },
        "queue_info": {}
    }
    
    # Count job statuses
    for job_key in processed_keys:
        status = redis_client.hget(job_key, "status")
        if status:
            if status in stats["status_counts"]:
                stats["status_counts"][status] += 1
    
    # Get Celery queue info
    try:
        celery_inspect = celery_app.control.inspect()
        stats["queue_info"]["active"] = celery_inspect.active()
        stats["queue_info"]["scheduled"] = celery_inspect.scheduled()
        stats["queue_info"]["reserved"] = celery_inspect.reserved()
    except Exception as e:
        stats["queue_info"]["error"] = str(e)
    # Corrections metrics (best-effort import to avoid tight coupling)
    try:
        from api.corrections_api import invalid_shape_count_last, COUNTERS  # type: ignore
        stats["corrections_invalid_shape_last_15m"] = invalid_shape_count_last(15)
        stats["corrections_save_counters"] = {
            "attempted": COUNTERS.get("corrections.save.attempted", 0),
            "succeeded": COUNTERS.get("corrections.save.succeeded", 0),
            "failed_wrong_type": COUNTERS.get("corrections.save.failed_wrong_type", 0),
        }
    except Exception:
        pass
    
    return stats


@app.get("/files/{job_id}/original-pdf", tags=["files"])
async def get_original_pdf(job_id: str):
    """Get original PDF file for a job (for PDF viewer integration)"""
    base_id = normalize_result_id(job_id)

    # Check both inbox and processing directories for the PDF
    pdf_paths = [
        INBOX_DIR / f"{base_id}.pdf",
        INBOX_DIR / f"{job_id}.pdf",  # Try with original job ID format too
        DATA_DIR / f"{base_id}.pdf",
        DATA_DIR / f"{job_id}.pdf"
    ]

    pdf_file = None
    for path in pdf_paths:
        if path.exists():
            pdf_file = path
            break

    if not pdf_file:
        raise HTTPException(status_code=404, detail="Original PDF not found")

    # Serve inline to be friendlier to PDF.js and in-browser viewers
    headers = {
        'Content-Disposition': f'inline; filename="lab_report_{base_id}.pdf"',
        'Accept-Ranges': 'bytes',
    }
    return FileResponse(
        path=pdf_file,
        media_type='application/pdf',
        headers=headers,
    )

@app.get("/files/{directory}/{filename}", tags=["results"])
async def get_file(directory: str, filename: str):
    """Get a file from data directories (outbox, expected, etc.)"""
    
    # Validate directory to prevent path traversal
    allowed_dirs = ["outbox", "expected", "training", "labelstudio"]
    if directory not in allowed_dirs:
        raise HTTPException(status_code=400, detail=f"Directory '{directory}' not allowed")
    
    # Validate filename
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = DATA_DIR / directory / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = json.load(f)
        return content
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")


@app.post("/golden/promote/{job_id}", tags=["results"])
async def promote_to_golden(job_id: str):
    """Promote corrections from expected to golden set"""
    
    expected_file = DATA_DIR / "expected" / f"{job_id}.json"
    
    if not expected_file.exists():
        raise HTTPException(status_code=404, detail="Expected file not found")
    
    try:
        # Create golden directory if it doesn't exist
        golden_dir = DATA_DIR / "golden"
        golden_dir.mkdir(exist_ok=True)
        
        golden_file = golden_dir / f"{job_id}.json"
        
        # Read the corrected data
        with open(expected_file, 'r', encoding='utf-8') as f:
            corrected_data = json.load(f)
        
        # Add golden set metadata
        golden_data = {
            "job_id": job_id,
            "promoted_at": datetime.utcnow().isoformat(),
            "source": "manual_corrections",
            "version": "1.0",
            "data": corrected_data
        }
        
        # Write to golden set
        with open(golden_file, 'w', encoding='utf-8') as f:
            json.dump(golden_data, f, indent=2, ensure_ascii=False)
        
        # Log the promotion
        redis_client.lpush(
            f"job:{job_id}:logs",
            json.dumps({
                "timestamp": datetime.utcnow().isoformat(),
                "level": "info",
                "message": f"Corrections promoted to golden set: {golden_file}",
                "stage": "golden_promotion"
            })
        )
        
        return {
            "message": "Successfully promoted to golden set",
            "golden_file": str(golden_file),
            "promoted_at": golden_data["promoted_at"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error promoting to golden: {str(e)}")


@app.get("/golden", tags=["results"])
async def list_golden_set():
    """List all files in the golden set"""
    
    golden_dir = DATA_DIR / "golden"
    
    if not golden_dir.exists():
        return {"golden_files": [], "total": 0}
    
    golden_files = []
    
    for file_path in golden_dir.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                golden_data = json.load(f)
            
            golden_files.append({
                "job_id": golden_data.get("job_id", file_path.stem),
                "filename": file_path.name,
                "promoted_at": golden_data.get("promoted_at"),
                "version": golden_data.get("version", "unknown"),
                "source": golden_data.get("source", "unknown")
            })
            
        except Exception as e:
            # Include broken files in the list but mark them
            golden_files.append({
                "job_id": file_path.stem,
                "filename": file_path.name,
                "error": f"Failed to read: {str(e)}"
            })
    
    # Sort by promotion date (newest first)
    golden_files.sort(key=lambda x: x.get("promoted_at", ""), reverse=True)
    
    return {
        "golden_files": golden_files,
        "total": len(golden_files)
    }


# Corrections API routes
@app.post("/results/{result_id}/corrections", tags=["corrections"])
async def save_corrections(result_id: str, request: Request, payload: CorrectionsPayload):
    """Save corrections for a result"""
    logger.info("Saving corrections for %s | content-type=%s", result_id, request.headers.get("content-type"))
    raw = await request.body()
    logger.info("Raw body: %s", raw.decode("utf-8", "ignore"))
    
    try:
        base_id = normalize_result_id(result_id)
        
        corrections_data = {
            "result_id": result_id,
            "base_id": base_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "corrections": payload.corrections
        }
        
        logger.info("Parsed JSON: %s", payload.dict())
        _save_corrections(base_id, corrections_data)

        # PHI-safe keys preview: prefer 'path' if present; otherwise 'line_number:field'
        keys: List[str] = []
        for item in payload.corrections:
            p = item.get("path")
            if isinstance(p, str) and p:
                keys.append(p)
            else:
                ln = item.get("line_number")
                field = item.get("field")
                if field:
                    keys.append(f"{ln}:{field}" if ln is not None else f"?:{field}")
        keys_preview = ", ".join(keys[:5]) + (f" (+{len(keys)-5} more)" if len(keys) > 5 else "")
        logger.info(
            "Corrections saved | base_id=%s saved=%d keys=[%s]",
            base_id,
            len(payload.corrections),
            keys_preview,
        )

        return {"ok": True, "message": "Corrections saved", "base_id": base_id}
    except Exception as e:
        logger.error("Failed to save corrections for %s: %s", result_id, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to save corrections: {e}")

@app.get("/results/{result_id}/corrections", tags=["corrections"])
async def get_corrections(result_id: str):
    """Get corrections for a result"""
    base_id = normalize_result_id(result_id)
    
    try:
        return _load_corrections(base_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load corrections: {e}")

@app.get("/review/{result_id}/corrections", tags=["review"])
async def get_review_corrections(result_id: str):
    """Get corrections for a result (alias to results endpoint)"""
    return await get_corrections(result_id)


@app.post("/review/{result_id}/training", tags=["review"])
async def add_training_data(result_id: str, payload: TrainingPayload):
    """Add training data for a result"""
    base_id = normalize_result_id(result_id)
    
    # Ensure TRAINING_DIR exists
    training_dir = DATA_DIR / "training"
    training_dir.mkdir(parents=True, exist_ok=True)
    
    # Load corrections if requested
    corrections = []
    if payload.include_manual_corrections:
        corrections_data = _load_corrections(base_id)
        corrections = corrections_data.get("corrections", [])
    
    # Create training entry
    training_entry = {
        "result": result_id,
        "corrections": corrections,
        "source_id": base_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "annotations": payload.annotations or [],
        "include_manual_corrections": payload.include_manual_corrections
    }
    
    # Append to training JSONL file
    training_file = training_dir / f"{base_id}.training.jsonl"
    try:
        with open(training_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(training_entry, ensure_ascii=False) + "\n")
        
        return {"ok": True, "message": "Training data saved", "base_id": base_id, "path": str(training_file)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save training data: {e}")


@app.get("/files/{result_id}/extracted-text", tags=["files"])
async def get_extracted_text(result_id: str):
    """Get extracted text for a result"""
    base_id = normalize_result_id(result_id)
    
    extracted_file = DATA_DIR / f"{base_id}.extracted.txt"
    
    if not extracted_file.exists():
        raise HTTPException(status_code=404, detail="not found")
    
    try:
        text = extracted_file.read_text(encoding="utf-8")
        return {"text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read extracted text: {e}")

@app.get("/results/{result_id}/extracted-text", tags=["results"])
async def get_results_extracted_text(result_id: str):
    """Get extracted text for a result (compatibility alias)"""
    return await get_extracted_text(result_id)



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
