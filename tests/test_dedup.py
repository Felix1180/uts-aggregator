import os
import tempfile
from src.dedup_store import DedupStore

def test_dedup_basic():
    fd, path = tempfile.mkstemp(prefix="deduptest_", suffix=".db")
    os.close(fd)
    try:
        store = DedupStore(path)
        assert store.try_mark_processed("t1", "e1") is True
        # second attempt should be duplicate
        assert store.try_mark_processed("t1", "e1") is False
        store.persist_event("t1", "e1", "2025-10-23T00:00:00Z", "src", {"a":1})
        evts = store.get_events("t1", limit=10)
        assert len(evts) == 1
    finally:
        store.close()
        os.remove(path)