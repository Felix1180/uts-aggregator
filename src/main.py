import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
import uvicorn

from .models import EventModel
from .dedup_store import DedupStore

# =================== CONFIG ===================
DATABASE = os.getenv("DATABASE_PATH", "data/dedup.db")
QUEUE_MAXSIZE = int(os.getenv("QUEUE_MAXSIZE", "10000"))

# =================== LOGGING ===================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("aggregator")

# =================== FASTAPI APP ===================
app = FastAPI(title="PubSub Log Aggregator (Idempotent Consumer + Dedup)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =================== GLOBAL STATE ===================
store = DedupStore(DATABASE)
event_queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
shutdown_event = asyncio.Event()

start_time = datetime.utcnow()
stats = {
    "received": 0,
    "unique_processed": 0,
    "duplicate_dropped": 0
}

consumer_task = None

# =================== CONSUMER LOOP ===================
async def consumer_loop():
    logger.info("Consumer loop started.")
    while not shutdown_event.is_set():
        try:
            evt = await event_queue.get()
        except asyncio.CancelledError:
            break
        try:
            topic = evt["topic"]
            event_id = evt["event_id"]
            ts = evt["timestamp"]
            source = evt["source"]
            payload = evt["payload"]

            # Dedup check (atomic)
            if store.try_mark_processed(topic, event_id):
                store.persist_event(topic, event_id, ts, source, payload)
                stats["unique_processed"] += 1
                logger.info(f"✅ Processed event topic={topic} event_id={event_id}")
            else:
                stats["duplicate_dropped"] += 1
                logger.warning(f"⚠️ Duplicate dropped topic={topic} event_id={event_id}")
        except Exception as e:
            logger.exception("Error processing event: %s", e)
        finally:
            event_queue.task_done()

    logger.info("Consumer loop stopped.")


def start_consumer_background(loop=None):
    """Start consumer in background (used by startup and tests)"""
    global consumer_task
    if consumer_task is None or consumer_task.done():
        if loop is None:
            loop = asyncio.get_event_loop()
        consumer_task = loop.create_task(consumer_loop())


# =================== FASTAPI LIFECYCLE ===================
@app.on_event("startup")
async def ensure_consumer_for_tests():
    """Pastikan consumer loop aktif juga saat dijalankan lewat TestClient (pytest)"""
    if consumer_task is None or consumer_task.done():
        loop = asyncio.get_event_loop()
        start_consumer_background(loop)


@app.on_event("shutdown")
async def shutdown():
    logger.info("🛑 Shutting down aggregator app.")
    shutdown_event.set()
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
    store.close()


# =================== ROUTES ===================

@app.post("/publish")
async def publish(request: Request):
    """Accept single or batch event(s)"""
    body = await request.json()
    events = [body] if isinstance(body, dict) else body if isinstance(body, list) else None
    if not events:
        raise HTTPException(status_code=400, detail="Body must be an object or array.")

    accepted = 0
    errors = []
    for idx, raw in enumerate(events):
        try:
            evt = EventModel(**raw)
            try:
                event_queue.put_nowait(evt.dict())
                stats["received"] += 1
                accepted += 1
            except asyncio.QueueFull:
                raise HTTPException(status_code=503, detail="Internal queue full, try later.")
        except Exception as e:
            errors.append({"index": idx, "error": str(e)})

    return JSONResponse({"accepted": accepted, "errors": errors})


@app.get("/events")
async def get_events(topic: Optional[str] = Query(None), limit: int = Query(1000)):
    evts = store.get_events(topic, limit)
    return {"count": len(evts), "events": evts}


@app.get("/stats")
async def get_stats():
    uptime_seconds = (datetime.utcnow() - start_time).total_seconds()
    return {
        "received": stats["received"],
        "unique_processed": stats["unique_processed"],
        "duplicate_dropped": stats["duplicate_dropped"],
        "topics": store.list_topics(),
        "uptime_seconds": uptime_seconds
    }

# =================== TEST ENVIRONMENT SUPPORT ===================
if os.getenv("PYTEST_CURRENT_TEST") is not None:
    start_consumer_background()

# =================== MAIN ENTRY ===================
if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=False)
