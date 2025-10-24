import pytest
import asyncio
import httpx
import time
from datetime import datetime

BASE_URL = "http://localhost:8080"  # pastikan server aggregator jalan di port ini


@pytest.mark.asyncio
async def test_stress_large_batch():
    async with httpx.AsyncClient(timeout=10.0) as client:
        total_events = 5000
        duplicate_ratio = 0.2
        unique_events = int(total_events * (1 - duplicate_ratio))

        events = []
        now = datetime.utcnow().isoformat()
        for i in range(unique_events):
            event = {
                "topic": "sensor",
                "event_id": f"evt-{i}",
                "timestamp": now,
                "source": "stress_test",
                "payload": {"value": i},
            }
            events.append(event)

        # tambahkan 20% duplikat
        duplicates = events[: int(unique_events * duplicate_ratio)]
        all_events = events + duplicates

        start = time.time()
        res = await client.post(f"{BASE_URL}/publish", json=all_events)
        elapsed = time.time() - start
        assert res.status_code == 200, res.text

        # beri waktu consumer untuk proses semua (max 5 detik)
        for _ in range(50):
            stats = await client.get(f"{BASE_URL}/stats")
            data = stats.json()
            if data["unique_processed"] >= unique_events:
                break
            await asyncio.sleep(0.1)

        stats = await client.get(f"{BASE_URL}/stats")
        data = stats.json()

        print(f"\nPublish {total_events} event selesai dalam {elapsed:.2f}s")
        print(f"Stats: {data}")

        assert data["received"] >= total_events
        assert data["unique_processed"] == unique_events
        assert data["duplicate_dropped"] >= len(duplicates)
        assert elapsed <= 5.0, "Proses terlalu lambat untuk 5000 event"
