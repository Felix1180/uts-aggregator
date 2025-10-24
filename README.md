# UTS — Pub-Sub Log Aggregator (Idempotent Consumer + Deduplication)

## Struktur

(lihat di README awal dari pesan)

## Requirements

- Docker (opsional)
- Python 3.11 (untuk running lokal)
- pip install -r requirements.txt

## Build & Run (Docker)

Build image:
docker build -t uts-aggregator .

Run:
docker run -p 8080:8080 -v $(pwd)/data:/app/data uts-aggregator

## Run locally (without Docker)

pip install -r requirements.txt
export DATABASE_PATH=./data/dedup.db
python -m src.main

## Endpoints

POST /publish

- JSON single event or array of events. Event schema:
  { "topic": "string", "event_id": "string-unik", "timestamp": "ISO8601", "source": "string", "payload": { ... } }

GET /events?topic=...&limit=1000

- Returns unique processed events

GET /stats

- Returns received, unique_processed, duplicate_dropped, topics, uptime_seconds

## Tests

pytest

## Notes

- Dedup store uses SQLite database at `DATABASE_PATH` (default `/app/data/dedup.db`) and persists processed ids.
- Idempotency achieved by SQLite PRIMARY KEY on (topic,event_id) and atomic INSERT.