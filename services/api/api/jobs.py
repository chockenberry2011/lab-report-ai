from fastapi import APIRouter, Query
from typing import Optional, List, Dict, Any
import os, time, redis
from datetime import datetime

router = APIRouter()
r = redis.Redis.from_url(os.getenv("REDIS_URL","redis://redis:6379/0"), decode_responses=True)

def _parse_ts(*vals: str) -> float:
    for v in vals:
        if not v:
            continue
        try:
            return datetime.fromisoformat(v).timestamp()
        except Exception:
            continue
    # last resort: now (keeps order stable enough)
    return float(r.time()[0])

def _ids_for_status(status: Optional[str]) -> List[str]:
    if status:
        return sorted(r.smembers(f"jobs:status:{status}"))
    # Prefer index if present
    if r.exists("jobs:index"):
        return list(r.zrevrange("jobs:index", 0, -1))
    # Fallback to all
    return sorted(r.smembers("jobs:all"))

def _job_summary(jid: str) -> Dict[str, Any]:
    h = r.hgetall(f"job:{jid}") or {}
    return {
        "id": jid,
        "status": h.get("status") or "unknown",
        "created_at": h.get("created_at"),
        "updated_at": h.get("updated_at") or h.get("created_at"),
        "error": h.get("error"),
        "filename": h.get("filename"),
        "source": h.get("source"),
    }

@router.get("/jobs")
def list_jobs(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    ids = _ids_for_status(status)

    # If we didn't use the ZSET, sort by updated_at desc ourselves
    if not r.exists("jobs:index"):
        ids.sort(
            key=lambda j: _parse_ts(
                r.hget(f"job:{j}", "updated_at"),
                r.hget(f"job:{j}", "created_at"),
            ),
            reverse=True,
        )

    # If a status was asked for and the set is empty, filter manually from the full list
    if status and not ids:
        ids = [
            j for j in _ids_for_status(None)
            if (r.hget(f"job:{j}", "status") or "").lower() == status.lower()
        ]

    total = len(ids)
    start, end = (page - 1) * per_page, (page - 1) * per_page + per_page
    page_ids = ids[start:end]

    return {
        "jobs": [_job_summary(j) for j in page_ids],
        "total": total,
        "page": page,
        "per_page": per_page,
        "has_next": end < total,
    }
