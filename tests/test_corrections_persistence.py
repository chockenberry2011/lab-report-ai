import json
from pathlib import Path
import pytest


def get_client():
    try:
        from services.api.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    except Exception:
        return None


@pytest.mark.parametrize("suffix", ["", ".debug", ".03_compose.debug"])
def test_corrections_roundtrip(tmp_path, monkeypatch, suffix):
    client = get_client()
    if client is None:
        pytest.skip("FastAPI dependencies not available")

    # Use isolated RESULT dir
    monkeypatch.setenv("RESULTS_DIR", str(tmp_path))

    # Prepare outbox with a compose file for the variant id so compose reads work if needed
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir()

    from services.api.api import results as results_module
    original_outbox = results_module.OUTBOX
    results_module.OUTBOX = outbox_dir

    base_id = "abcd-efgh"
    rid = base_id + suffix

    # Minimal compose document
    compose_doc = {
        "lab_panels": [
            {
                "name": "P",
                "test_rows": [
                    {"line_number": 1, "text": "A", "test_name": "A", "result_value": "1", "units": "x"},
                    {"line_number": 2, "text": "B", "test_name": "B", "result_value": "2", "units": "y"},
                ],
            }
        ]
    }
    (outbox_dir / f"{rid}.json").write_text(json.dumps(compose_doc))

    try:
        payload = {
            "corrections": [
                {"line_number": 2, "field": "units", "new_value": "mg/dL"},
            ]
        }
        r = client.post(f"/results/{rid}/corrections", json=payload)
        assert r.status_code == 200, r.text

        r = client.get(f"/results/{rid}/corrections")
        assert r.status_code == 200
        data = r.json()
        # Accept both list shape or object-with-list depending on router
        if isinstance(data, list):
            assert len(data) >= 1
        elif isinstance(data, dict):
            assert any(isinstance(v, list) and len(v) >= 1 for v in data.values())
        else:
            pytest.fail(f"Unexpected corrections shape: {type(data)}")

        # Compose should reflect saved correction after reload
        g = client.get(f"/results/{rid}")
        assert g.status_code == 200, g.text
        doc = g.json()
        # find line_number 2
        line2 = None
        for p in doc.get("lab_panels", []):
            for tr in p.get("test_rows", []):
                if tr.get("line_number") == 2:
                    line2 = tr
                    break
        assert line2 is not None
        assert line2.get("units") == "mg/dL"

        # Fresh client
        from services.api.api.main import app
        from fastapi.testclient import TestClient
        fresh = TestClient(app)
        g2 = fresh.get(f"/results/{rid}")
        assert g2.status_code == 200
        doc2 = g2.json()
        line2b = None
        for p in doc2.get("lab_panels", []):
            for tr in p.get("test_rows", []):
                if tr.get("line_number") == 2:
                    line2b = tr
                    break
        assert line2b is not None
        assert line2b.get("units") == "mg/dL"
    finally:
        results_module.OUTBOX = original_outbox

