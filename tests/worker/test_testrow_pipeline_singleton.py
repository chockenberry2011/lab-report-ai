import types


def _fake_pipeline_for(text_sample: str):
    class FakePipeline:
        name = "test-pipeline"

        def predict(self, tokens):
            # Very simple tagging based on the provided sample
            # Assume format: NAME VALUE FLAG UNIT RANGE
            tags = ["O"] * len(tokens)
            if not tokens:
                return tags
            # First token is name (may be multi-token, handle Creatinine case)
            tags[0] = "B-TEST_NAME"
            # Find value (first token with digit)
            value_idx = next((i for i, t in enumerate(tokens) if any(ch.isdigit() for ch in t)), None)
            if value_idx is not None:
                tags[value_idx] = "B-VALUE"
            # Simple unit detection
            for i, w in enumerate(tokens):
                wl = w.lower()
                if wl in ("mg/dl", "mmol/l", "g/dl", "iu/l", "u/l", "ng/ml", "%"):
                    tags[i] = "B-UNIT"
                    break
            # Flag
            for i, w in enumerate(tokens):
                if w.upper() in ("H", "L", "HIGH", "LOW"):
                    tags[i] = "B-FLAG"
                    break
            # Ref range like 0.76-1.27
            for i, w in enumerate(tokens):
                if any(ch.isdigit() for ch in w) and ("-" in w or "–" in w):
                    tags[i] = "B-REF_RANGE"
                    break
            return tags

        def predict_proba(self, tokens):
            return [{"O": 0.9} for _ in tokens]

    return FakePipeline()


def test_parse_sample_row_ml_no_fallback(monkeypatch):
    import services.worker.tasks as tasks

    sample = "Creatinine 1.50 High mg/dL 0.76-1.27"

    # Ensure pipeline exists
    monkeypatch.setattr(tasks, "_testrow_pipeline", _fake_pipeline_for(sample), raising=False)
    monkeypatch.setattr(tasks, "_testrow_model_ok", True, raising=False)
    monkeypatch.setattr(tasks, "_testrow_used_fallback_last", None, raising=False)

    role_result = {
        "lines": [
            {"text": sample, "predicted_role": "TEST_ROW"}
        ]
    }

    res = tasks.process_test_rows(role_result, config={})
    row = res["test_rows"][0]
    meta = res["testrow_meta"]

    assert row.get("test_name") is not None
    assert row.get("result_value") is not None
    assert row.get("units") in ("mg/dL", "mg/dl")
    assert row.get("reference_range") is not None
    assert row.get("flags") == ["H"] or row.get("flags") == ["HIGH"]
    assert meta["fallback"] is False
    assert meta["engine"] == "ml"


def test_reinit_when_pipeline_none(monkeypatch):
    import services.worker.tasks as tasks

    sample = "Creatinine 1.50 High mg/dL 0.76-1.27"

    # Start with no pipeline, and ensure build returns one
    monkeypatch.setattr(tasks, "_testrow_pipeline", None, raising=False)
    monkeypatch.setattr(tasks, "build_testrow_pipeline", lambda: _fake_pipeline_for(sample), raising=True)

    role_result = {
        "lines": [
            {"text": sample, "predicted_role": "TEST_ROW"}
        ]
    }

    res = tasks.process_test_rows(role_result, config={})
    assert res["testrow_meta"]["fallback"] is False
    row = res["test_rows"][0]
    assert row.get("test_name") is not None


def test_compose_quality_metrics_no_rule_fallback_reason(monkeypatch):
    import services.worker.tasks as tasks

    # Build a minimal role_result with a panel and a test row
    lines = [
        {"page": 1, "line_number": 10, "text": "COMPREHENSIVE METABOLIC PANEL", "predicted_role": "SECTION_PANEL", "y_norm": 0.15},
        {"page": 1, "line_number": 11, "text": "Creatinine 1.50 High mg/dL 0.76-1.27", "predicted_role": "TEST_ROW", "y_norm": 0.18},
    ]

    role_result = {"lines": lines}

    # Ensure pipeline is available
    monkeypatch.setattr(tasks, "_testrow_pipeline", _fake_pipeline_for(lines[1]["text"]), raising=False)
    monkeypatch.setattr(tasks, "_testrow_used_fallback_last", False, raising=False)

    testrow_result = tasks.process_test_rows(role_result, config={})
    compose_res = tasks.compose_panels(testrow_result, role_result, config={}, classifier_probabilities=None)

    reasons = compose_res["quality_metrics"].get("review_reasons", []) or []
    assert "Test row parsing used rule-based fallback" not in reasons

