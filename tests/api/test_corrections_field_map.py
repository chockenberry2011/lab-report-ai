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
        import importlib
        import api.api.main as api_main
        api_main.DATA_DIR = Path(tmpdir)  # force
        yield Path(tmpdir)
        if original is not None:
            os.environ["DATA_DIR"] = original
        else:
            os.environ.pop("DATA_DIR", None)


@pytest.fixture
def client(temp_data_dir):
    return TestClient(app)


def test_vendor_name_alias_resolves_and_persists(client, temp_data_dir: Path):
    rid = "abc-123.debug"
    payload = {
        "corrections": [
            {"field": "vendor.name", "new_value": "Acme Co"}
        ]
    }
    r = client.post(f"/results/{rid}/corrections", json=payload)
    assert r.status_code == 200, r.text

    # Verify persisted file contains canonical field and value
    base_id = rid.split(".", 1)[0]
    p = temp_data_dir / "results" / base_id / "corrections.json"
    assert p.exists()
    data = json.loads(p.read_text())
    assert isinstance(data, list)
    assert data[0]["field"] == "vendor_name"
    assert data[0]["value"] == "Acme Co"


def test_required_field_empty_returns_400(client, temp_data_dir: Path):
    rid = "abc-123.debug"
    payload = {"corrections": [{"field": "vendor.name", "new_value": ""}]}
    r = client.post(f"/results/{rid}/corrections", json=payload)
    assert r.status_code == 400
    body = r.json()
    # FastAPI packs detail when we raised HTTPException with dict detail
    assert body.get("detail", {}).get("error") == "value_required"
    assert body.get("detail", {}).get("field") == "vendor.name"


def test_schema_fields_endpoint(client):
    r = client.get("/schema/fields")
    assert r.status_code == 200
    d = r.json()
    assert "fields" in d
    fields = d["fields"]
    assert "vendor_name" in fields
    assert "aliases" in fields["vendor_name"]
    assert "vendor.name" in fields["vendor_name"]["aliases"]
    assert fields["vendor_name"]["required"] is True

