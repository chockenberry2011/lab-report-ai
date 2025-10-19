# Health Endpoint Test Commands

## Build and Start API
```bash
# Using the new Makefile target
make api-restart

# Or manually
docker compose build api
docker compose up -d api
sleep 1
```

## Test Endpoints
```bash
# Test ping endpoint
curl -sf http://localhost:8000/healthz/ping

# Expected response:
{"ok": true}

# Test models endpoint  
curl -sf http://localhost:8000/healthz/models

# Test environment variables endpoint
curl -sf http://localhost:8000/healthz/env

# Test Python paths endpoint
curl -sf http://localhost:8000/healthz/paths

# Expected models response (with placeholder models):
{
  "roles_model_exists": true,
  "testrow_model_exists": true,
  "roles_is_placeholder": true,
  "testrow_is_placeholder": true,
  "roles_model_ok": false,
  "testrow_model_ok": false,
  "roles_used_fallback_last": null,
  "testrow_used_fallback_last": null,
  "import_error": null
}

# Expected env response (Docker environment):
{
  "MODEL_ROLES_DIR": "/models/roles",
  "MODEL_TESTROW_DIR": "/models/testrow", 
  "REDIS_URL": "redis://redis:6379"
}

# Expected paths response (Docker container):
{
  "sys_path": ["/app", "/usr/local/lib/python3.11/site-packages", "..."]
}
```

## Smoke Test
```bash
# Inside Docker container
docker compose exec api python scripts/smoke_healthz.py

# Expected output:
healthz import OK: /app/healthz.py
```

## Corrections Sanity Checks

### JSON Format
```bash
curl -sS -X POST 'http://localhost:8000/results/TEST.03_compose.debug/corrections' \
 -H 'Content-Type: application/json' \
 -d '{"items":[
   {"path":"lab_panels[0].test_rows[2].result_value","value":"72","op":"replace"},
   {"path":"$.lab_panels[0].test_rows[2].units","value":"mg/dL"}
 ]}'
```

### Form-encoded (should also work)
```bash
curl -sS -X POST 'http://localhost:8000/results/TEST.03_compose.debug/corrections' \
 -H 'Content-Type: application/x-www-form-urlencoded' \
 --data-urlencode 'items=[{"path":"a.b[0]","value":1}]'
```

After running the first command, `results/TEST.03_compose.debug/corrections.jsonl` should contain 2 lines.

## API Documentation
The endpoints will be available in the FastAPI automatic docs at:
- http://localhost:8000/docs#/health

Endpoints:
- `GET /healthz/ping` - Simple health check
- `GET /healthz/models` - Model status with fallback information
- `GET /healthz/env` - Environment variables (MODEL_ROLES_DIR, MODEL_TESTROW_DIR, REDIS_URL)
- `GET /healthz/paths` - Python sys.path (first 5 entries)