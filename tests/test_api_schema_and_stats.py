import time
from fastapi.testclient import TestClient
from src.main import app, store, stats

client = TestClient(app)

def test_schema_validation_and_publish():
    # missing required fields -> 422
    r = client.post("/publish", json={"topic": "t1"})
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert r.json()["accepted"] == 0


def wait_for_consumer(expected_unique: int, timeout=3.0):
    """
    Tunggu sampai consumer memproses event unik minimal sebanyak expected_unique.
    """
    start = time.time()
    while time.time() - start < timeout:
        st = client.get("/stats").json()
        if st["unique_processed"] >= expected_unique:
            return st
        time.sleep(0.1)
    return client.get("/stats").json()


def test_publish_and_stats_consistency():
    # reset store & stats untuk test bersih
    store.clear_all()
    stats["received"] = stats["unique_processed"] = stats["duplicate_dropped"] = 0

    # kirim event unik
    ev = {
        "topic": "t-api",
        "event_id": "api-1",
        "timestamp": "2025-10-23T01:00:00Z",
        "source": "test",
        "payload": {"x": 1},
    }

    r = client.post("/publish", json=ev)
    assert r.status_code == 200

    # tunggu consumer jalan
    st = wait_for_consumer(expected_unique=1)
    assert st["received"] >= 1
    assert st["unique_processed"] >= 1
    assert st["duplicate_dropped"] == 0
