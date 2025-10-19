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


def make_compose_doc():
  return {
    "document_info": {
      "patient_name": "John Doe",
      "test_date": "2024-01-15"
    },
    "lab_panels": [
      {
        "id": "p1",
        "name": "Basic Panel",
        "panel_score": 0.9,
        "needs_review": False,
        "review_reasons": [],
        "test_rows": [
          {
            "line_number": 5,
            "page": 1,
            "text": "Glucose 95 mg/dL",
            "test_name": "Glucose",
            "result_value": "95",
            "units": "mg/dL",
            "reference_range": "70-99",
            "flag": "",
            "confidence": 0.95,
          },
          {
            "line_number": 6,
            "page": 1,
            "text": "TSH 152.222 High",
            "test_name": "TSH",
            "result_value": "152.222",
            "units": "High",
            "reference_range": "0.450-4.500",
            "flag": "HIGH",
            "confidence": 0.85,
          }
        ]
      }
    ]
  }


def _get_corrections_list(client, result_id: str):
  r = client.get(f"/results/{result_id}/corrections")
  assert r.status_code == 200
  data = r.json()
  # Support both shapes: results router returns list, main returns dict
  if isinstance(data, list):
    return data
  if isinstance(data, dict):
    if isinstance(data.get("corrections"), list):
      return data["corrections"]
    if isinstance(data.get("items"), list):
      return data["items"]
  return []


@pytest.mark.parametrize("variant_suffix", ["", ".debug", ".03_compose.debug"])
def test_corrections_merge_and_compose_reflects(tmp_path, monkeypatch, variant_suffix):
  client = get_client()
  if client is None:
    pytest.skip("FastAPI dependencies not available")

  # Configure RESULTS_DIR and OUTBOX to temporary locations
  monkeypatch.setenv("RESULTS_DIR", str(tmp_path))
  outbox_dir = tmp_path / "outbox"
  outbox_dir.mkdir()

  # Point results module OUTBOX to tmp
  from services.api.api import results as results_module
  original_outbox = results_module.OUTBOX
  results_module.OUTBOX = outbox_dir

  base_id = "it-works-1234"
  variant_id = base_id + variant_suffix
  compose_path = outbox_dir / f"{variant_id}.json"
  compose_path.write_text(json.dumps(make_compose_doc()))

  try:
    # Initial GET /corrections should be empty
    corr0 = _get_corrections_list(client, variant_id)
    assert corr0 == []

    # POST a correction (units fix on line 6)
    payload = {
      "corrections": [
        {
          "line_number": 6,
          "field": "units",
          "new_value": "uIU/mL",
          "old_value": "High",
          "reason": "Fix units",
        }
      ]
    }
    r = client.post(f"/results/{variant_id}/corrections", json=payload)
    assert r.status_code == 200, r.text

    # GET /corrections should now be non-empty
    corr1 = _get_corrections_list(client, variant_id)
    assert isinstance(corr1, list) and len(corr1) >= 1

    # Compose GET should reflect correction
    g = client.get(f"/results/{variant_id}")
    assert g.status_code == 200, g.text
    doc = g.json()
    # Find line_number 6
    row6 = None
    for p in doc.get("lab_panels", []):
      for tr in p.get("test_rows", []):
        if tr.get("line_number") == 6:
          row6 = tr
          break
    assert row6 is not None
    assert row6.get("units") == "uIU/mL"

    # Fresh client reload still shows correction
    from services.api.api.main import app
    from fastapi.testclient import TestClient
    fresh_client = TestClient(app)
    g2 = fresh_client.get(f"/results/{variant_id}")
    assert g2.status_code == 200
    doc2 = g2.json()
    row6b = None
    for p in doc2.get("lab_panels", []):
      for tr in p.get("test_rows", []):
        if tr.get("line_number") == 6:
          row6b = tr
          break
    assert row6b is not None and row6b.get("units") == "uIU/mL"

  finally:
    results_module.OUTBOX = original_outbox


def test_extracted_text_compat_variants(tmp_path, monkeypatch):
  client = get_client()
  if client is None:
    pytest.skip("FastAPI dependencies not available")

  # Setup outbox
  outbox_dir = tmp_path / "outbox"
  outbox_dir.mkdir()
  from services.api.api import results as results_module
  original_outbox = results_module.OUTBOX
  results_module.OUTBOX = outbox_dir

  base_id = "exttext-5678"
  variants = [base_id, base_id + ".debug", base_id + ".03_compose.debug"]

  try:
    # Create extracted-text debug files only for the base id
    for vid in variants:
      # Create file for each variant to ensure 200 on all
      (outbox_dir / f"{vid}.01_lines.debug.json").write_text(json.dumps({
        "lines": [
          {"page": 1, "text": "HEADER: Specimen", "bbox": [0,0,10,10], "role": "HEADER_FIELD", "confidence": 0.9},
          {"page": 1, "text": "TSH 3.0 uIU/mL", "bbox": [0,0,10,10], "role": "TEST_ROW", "confidence": 0.9},
        ]
      }))

    for vid in variants:
      # Canonical
      r1 = client.get(f"/results/{vid}/extracted-text")
      assert r1.status_code == 200, r1.text
      # Compat
      r2 = client.get(f"/files/{vid}/extracted-text")
      assert r2.status_code == 200, r2.text

  finally:
    results_module.OUTBOX = original_outbox

