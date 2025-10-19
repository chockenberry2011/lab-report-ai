import json
import os
from pathlib import Path

import pytest


def get_client():
    try:
        from services.api.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    except Exception:
        return None


@pytest.mark.parametrize("variants", [
    (
        "30dd8235-cc1c-4ef7-a9b7-99d8d8c94547",
        "30dd8235-cc1c-4ef7-a9b7-99d8d8c94547.debug",
        "30dd8235-cc1c-4ef7-a9b7-99d8d8c94547.03_compose.debug",
    )
])
def test_corrections_id_normalization_merges(tmp_path, monkeypatch, variants):
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")

    # Use isolated results dir
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))

    base_id, v_debug, v_compose = variants

    # Post corrections for each variant id
    payloads = [
        [
            {
                "field": "units",
                "new_value": "mg/dL",
                "line_number": 6,
                "reason": "units fix",
            }
        ],
        [
            {
                "field": "flag",
                "new_value": "HIGH",
                "line_number": 6,
                "reason": "flag fix",
            }
        ],
        [
            {
                "field": "test_name",
                "new_value": "TSH",
                "line_number": 6,
                "reason": "name fix",
            }
        ],
    ]

    ids = [base_id, v_debug, v_compose]

    for variant_id, payload in zip(ids, payloads):
        r = client.post(f"/results/{variant_id}/corrections", json={"corrections": payload})
        assert r.status_code == 200, r.text

    # All GETs should observe merged list of 3 corrections
    for variant_id in ids:
        g = client.get(f"/results/{variant_id}/corrections")
        assert g.status_code == 200, g.text
        data = g.json()
        # Support either shape: list (results router) or {"corrections": [...]} (main app)
        if isinstance(data, dict) and "corrections" in data:
            items = data["corrections"]
        else:
            items = data
        assert isinstance(items, list)
        assert len(items) == 3
