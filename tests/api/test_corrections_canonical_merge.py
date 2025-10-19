import os
import json
import tempfile
from pathlib import Path
import pytest

# Wire app import path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))

from fastapi.testclient import TestClient
from api.api.main import app


@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        original = os.environ.get("DATA_DIR")
        os.environ["DATA_DIR"] = tmpdir
        # ensure dirs
        Path(tmpdir, "outbox").mkdir(parents=True, exist_ok=True)
        Path(tmpdir, "results").mkdir(parents=True, exist_ok=True)
        # force reload of DATA_DIR reference
        import importlib
        import api.api.results as api_results
        import api.api.main as api_main
        api_results.DATA_ROOT = Path(tmpdir)
        api_results.OUTBOX = Path(tmpdir) / "outbox"
        api_results.RESULTS_DIR = Path(tmpdir) / "results"
        api_main.DATA_DIR = Path(tmpdir)
        yield Path(tmpdir)
        if original is not None:
            os.environ["DATA_DIR"] = original
        else:
            os.environ.pop("DATA_DIR", None)


@pytest.fixture
def client(temp_data_dir):
    return TestClient(app)


def test_vendor_name_canonical_merge(client, temp_data_dir: Path, caplog):
    rid = "abc-111"
    # Seed a compose debug doc in outbox as bootstrap source
    compose = {
        "document_info": {
            "vendor_name": "Old Vendor"
        },
        "lab_panels": []
    }
    (temp_data_dir / "outbox" / f"{rid}.03_compose.debug.json").write_text(json.dumps(compose), encoding="utf-8")

    # Post a canonical vendor_name change via alias
    payload = {"corrections": [{"field": "vendor.name", "new_value": "Acme Co"}]}
    r = client.post(f"/results/{rid}/corrections", json=payload)
    assert r.status_code == 200, r.text

    # GET should bootstrap canonical, apply corrections, persist back
    with caplog.at_level("INFO"):
        g = client.get(f"/results/{rid}")
    assert g.status_code == 200, g.text
    data = g.json()
    # document_info should reflect updated name
    assert data.get("document_info", {}).get("vendor", {}).get("name") == "Acme Co" or \
           data.get("document_info", {}).get("vendor_name") == "Acme Co"

    # Verify canonical file updated
    cfile = temp_data_dir / "results" / rid / f"{rid}.json"
    assert cfile.exists()
    cdoc = json.loads(cfile.read_text())
    # Accept either flat or nested depending on serializer
    assert cdoc.get("document_info", {}).get("vendor_name") == "Acme Co"

    # Compose logs should include applied=1
    assert any("compose_merge applied=1" in rec.message for rec in caplog.records), caplog.text
