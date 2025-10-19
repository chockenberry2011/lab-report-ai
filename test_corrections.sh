#!/bin/bash

# Test script for the corrections endpoint

echo "Testing corrections endpoint..."

# Test data
JOB_ID="XYZ123"
API_URL="http://localhost:8000"

# Test payload
PAYLOAD='{
  "job_id": "'$JOB_ID'",
  "tests": [
    {
      "line_index": 56,
      "test_name": "eGFR",
      "value": "52",
      "unit": "mL/min/1.73",
      "flag": "LOW",
      "ref_text": ">59"
    }
  ],
  "notes": "Test correction from manual review",
  "metadata": {
    "reviewed_by": "test_user",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'"
  }
}'

echo "Testing canonical endpoint: POST /results/$JOB_ID/corrections"
curl -X POST "$API_URL/results/$JOB_ID/corrections" \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD" \
  -v

echo ""
echo "Testing compatibility endpoint: POST /review/$JOB_ID/corrections"
curl -X POST "$API_URL/review/$JOB_ID/corrections" \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD" \
  -v

echo ""
echo "Testing debug routes endpoint: GET /debug/routes"
curl "$API_URL/debug/routes" -v

echo ""
echo "Test complete. Check for the corrections file at: /data/corrections/$JOB_ID/corrections.json"