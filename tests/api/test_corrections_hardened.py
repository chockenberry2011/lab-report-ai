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
        Path(tmpdir, "results").mkdir(parents=True, exist_ok=True)
        yield Path(tmpdir)
        if original is not None:
            os.environ["DATA_DIR"] = original
        else:
            os.environ.pop("DATA_DIR", None)


@pytest.fixture
def client(temp_data_dir):
    return TestClient(app)


def test_bad_content_type(client):
    rid = "x-1"
    r = client.post(f"/results/{rid}/corrections", data=b"[]", headers={"Content-Type": "text/plain"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "bad_content_type"
    assert "req_id" in body


def test_payload_must_be_array(client):
    rid = "x-2"
    r = client.post(f"/results/{rid}/corrections", json={"corrections": []})
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "payload_must_be_array"
    assert "req_id" in body


def test_unknown_field(client):
    rid = "x-3"
    r = client.post(f"/results/{rid}/corrections", json=[{"field": "foo", "value": "bar"}])
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "unknown_field"
    assert body["field"] == "foo"


def test_value_required(client):
    rid = "x-4"
    r = client.post(f"/results/{rid}/corrections", json=[{"field": "vendor.name", "value": ""}])
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "value_required"
    assert body["field"] == "vendor_name" or body["field"] == "vendor.name"


def test_happy_path(client, temp_data_dir: Path):
    rid = "x-5"
    # seed canonical doc
    cdir = temp_data_dir / "results" / rid
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / f"{rid}.json").write_text(json.dumps({"document_info": {"vendor_name": "Old"}, "lab_panels": []}), encoding="utf-8")
    r = client.post(f"/results/{rid}/corrections", json=[{"field": "vendor.name", "value": "Acme"}])
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "applied" in body
    # canonical should be updated
    doc = json.loads((cdir / f"{rid}.json").read_text())
    assert doc["document_info"]["vendor_name"] == "Acme"

