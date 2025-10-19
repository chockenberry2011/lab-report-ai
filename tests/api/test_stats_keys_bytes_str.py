from fastapi.testclient import TestClient


def test_stats_mixed_key_types(monkeypatch):
    from services.api.api.main import app
    client = TestClient(app)

    class FakeRedis:
        def keys(self, pattern):
            # Mix of bytes and str, including :logs entries which should be filtered
            return [b"job:1", "job:2", b"job:3:logs", "job:4:logs", "job:5"]

        def hget(self, key, field):
            # key will be str from the processed list in endpoint
            if key.endswith(":logs"):
                return None
            if key.endswith("job:1"):
                return "queued"
            if key.endswith("job:2"):
                return "completed"
            if key.endswith("job:5"):
                return "failed"
            return None

    # Patch redis_client used by the endpoint
    import services.api.api.main as main_mod
    monkeypatch.setattr(main_mod, "redis_client", FakeRedis())

    r = client.get("/stats")
    assert r.status_code == 200
    data = r.json()
    # Should count only job:1, job:2, job:5 (3 total) and exclude :logs
    assert data["total_jobs"] == 3
    assert data["status_counts"]["queued"] == 1
    assert data["status_counts"]["completed"] == 1
    assert data["status_counts"]["failed"] == 1

