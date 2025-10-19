import types


def test_model_adapter_smoke(monkeypatch):
    # Import the tasks module lazily to get module-level globals
    import services.worker.tasks as tasks

    class FakeAdapter:
        def __init__(self):
            self.called = False
            self.labels = [
                "O",
                "B-TEST_NAME",
                "I-TEST_NAME",
                "B-VALUE",
                "B-UNIT",
                "B-REF_RANGE",
                "B-FLAG",
            ]

        def predict(self, tokens):
            self.called = True
            # Simple deterministic tagging: first token is test name, find number and a unit
            tags = ["O"] * len(tokens)
            if tokens:
                tags[0] = "B-TEST_NAME"
            for i, w in enumerate(tokens):
                if any(ch.isdigit() for ch in w):
                    tags[i] = "B-VALUE"
                    break
            for i, w in enumerate(tokens):
                if w.lower() in ("mg/dl", "mmol/l", "g/dl"):
                    tags[i] = "B-UNIT"
                    break
            return tags

        def predict_proba(self, tokens):
            # Uniform confidences
            return [{"O": 0.9} for _ in tokens]

    fake = FakeAdapter()

    # Case 1: model available → should use adapter path
    # Set module-level pipeline singleton
    class FakePipeline:
        name = "test-pipeline"
        def predict(self, tokens):
            return fake.predict(tokens)
        def predict_proba(self, tokens):
            return fake.predict_proba(tokens)

    monkeypatch.setattr(tasks, "_testrow_pipeline", FakePipeline(), raising=False)
    monkeypatch.setattr(tasks, "_testrow_model_ok", True, raising=False)
    monkeypatch.setattr(tasks, "_testrow_used_fallback_last", None, raising=False)

    res = tasks.tag_testrow_line("Glucose 101 mg/dL 70-99 H")
    assert isinstance(res, dict)
    assert fake.called is True
    assert tasks._testrow_used_fallback_last is False
    assert len(res.get("tokens", [])) > 0

    # Case 2: model not available → should fall back
    fake.called = False
    monkeypatch.setattr(tasks, "_testrow_pipeline", None, raising=False)
    monkeypatch.setattr(tasks, "_testrow_model_ok", False, raising=False)
    res2 = tasks.tag_testrow_line("Glucose 101 mg/dL 70-99 H")
    assert isinstance(res2, dict)
    assert tasks._testrow_used_fallback_last is True
    assert fake.called is False
