import os
import tempfile
from src.dedup_store import DedupStore

def test_persistence_across_instances():
    fd, path = tempfile.mkstemp(prefix="deduptest_", suffix=".db")
    os.close(fd)
    try:
        s1 = DedupStore(path)
        assert s1.try_mark_processed("topicA", "id1") is True
        s1.persist_event("topicA", "id1", "2025-10-23T00:00:00Z", "src", {"k": "v"})
        s1.close()

        # simulate restart by creating new instance on same file
        s2 = DedupStore(path)
        # now try to mark same event -> should be duplicate
        assert s2.try_mark_processed("topicA", "id1") is False
        evts = s2.get_events("topicA")
        assert len(evts) == 1
        s2.close()
    finally:
        os.remove(path)