import time
import random
from fastapi.testclient import TestClient
from src.main import app, store, stats

client = TestClient(app)

def test_small_stress_100_events():
    # reset state
    store.clear_all()
    stats["received"] = stats["unique_processed"] = stats["duplicate_dropped"] = 0

    n = 100
    dup_rate = 0.2
    events = []
    for i in range(n):
        eid = f"stress-{i if random.random() > dup_rate else random.randint(0, max(0, i-1))}"
        events.append({
            "topic": "stress",
            "event_id": eid,
            "timestamp": "2025-10-23T02:00:00Z",
            "source": "stress-sim",
            "payload": {"i": i}
        })

    t0 = time.time()
    r = client.post("/publish", json=events)
    assert r.status_code == 200

    # tunggu consumer selesai (max 2 detik)
    for _ in range(20):
        st = client.get("/stats").json()
        if st["unique_processed"] >= int(n * (1 - dup_rate)) - 5:
            break
        time.sleep(0.1)

    t1 = time.time()
    st = client.get("/stats").json()

    # received harus sama atau lebih besar dari jumlah event
    assert st["received"] >= n
    # unique_processed mendekati jumlah unik
    assert st["unique_processed"] >= int(n * (1 - dup_rate)) - 5
    assert t1 - t0 < 10.0
