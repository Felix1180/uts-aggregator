import sqlite3
import threading
from typing import Optional, List, Tuple
import datetime
import json
import os

class DedupStore:
    """
    Simple SQLite-backed dedup store.
    Tables:
      dedup(topic TEXT, event_id TEXT, processed_at TEXT, PRIMARY KEY(topic,event_id))
      events(topic,...,payload TEXT, processed_at TEXT)
    """

    def __init__(self, db_path: str = "dedup.db"):
        self.db_path = db_path
        # ensure directory exists
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        # sqlite connection, allow access from multiple threads
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self.lock:
            cur = self.conn.cursor()
            # use WAL for better concurrency
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("""
            CREATE TABLE IF NOT EXISTS dedup (
                topic TEXT NOT NULL,
                event_id TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                PRIMARY KEY(topic,event_id)
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS events (
                topic TEXT NOT NULL,
                event_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                payload TEXT,
                processed_at TEXT NOT NULL,
                PRIMARY KEY(topic,event_id)
            );
            """)
            self.conn.commit()

    def try_mark_processed(self, topic: str, event_id: str) -> bool:
        """
        Atomically attempt to mark (topic,event_id) as processed.
        Returns True if it was NOT already processed (i.e., caller should process).
        Returns False if already existed (duplicate).
        """
        now = datetime.datetime.utcnow().isoformat() + "Z"
        with self.lock:
            cur = self.conn.cursor()
            try:
                # atomic insertion; will fail if primary key exists
                cur.execute(
                    "INSERT INTO dedup (topic, event_id, processed_at) VALUES (?, ?, ?);",
                    (topic, event_id, now)
                )
                self.conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def persist_event(self, topic, event_id, timestamp, source, payload):
        now = datetime.datetime.utcnow().isoformat() + "Z"
        payload_str = json.dumps(payload, ensure_ascii=False)
        with self.lock:
            cur = self.conn.cursor()
            # Insert or replace but dedup was already checked
            cur.execute("""
            INSERT OR REPLACE INTO events (topic, event_id, timestamp, source, payload, processed_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """, (topic, event_id, timestamp, source, payload_str, now))
            self.conn.commit()

    def get_events(self, topic: Optional[str] = None, limit: int = 1000) -> List[Tuple]:
        with self.lock:
            cur = self.conn.cursor()
            if topic:
                cur.execute("SELECT topic, event_id, timestamp, source, payload, processed_at FROM events WHERE topic=? ORDER BY processed_at LIMIT ?;", (topic, limit))
            else:
                cur.execute("SELECT topic, event_id, timestamp, source, payload, processed_at FROM events ORDER BY processed_at LIMIT ?;", (limit,))
            rows = cur.fetchall()
            # convert payload to dict
            results = []
            for r in rows:
                payload = json.loads(r[4]) if r[4] else {}
                results.append({
                    "topic": r[0],
                    "event_id": r[1],
                    "timestamp": r[2],
                    "source": r[3],
                    "payload": payload,
                    "processed_at": r[5]
                })
            return results

    def list_topics(self):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT topic FROM events;")
            return [r[0] for r in cur.fetchall()]

    def clear_all(self):
        """Menghapus semua data di tabel dedup dan events (untuk reset test)."""
        with self.lock:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM dedup;")
            cur.execute("DELETE FROM events;")
            self.conn.commit()

    def close(self):
        with self.lock:
            try:
                self.conn.commit()
            except:
                pass
            self.conn.close()