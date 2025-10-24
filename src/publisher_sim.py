import requests
import time
import uuid
import random
import argparse
from datetime import datetime

def make_event(topic, source, idx):
    eid = f"{source}-{idx}"
    if random.random() < 0.25:  # simulate duplicates sometimes by repeating id
        # reuse previous id occasionally
        eid = f"{source}-{random.randint(0, max(0, idx//2))}"
    evt = {
        "topic": topic,
        "event_id": eid,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "source": source,
        "payload": {"idx": idx}
    }
    return evt

def publish_batch(url, events):
    r = requests.post(url + "/publish", json=events, timeout=10)
    print("publish status", r.status_code, r.text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--url", type=str, default="http://localhost:8080")
    parser.add_argument("--topic", default="app.logs")
    parser.add_argument("--source", default="sim")
    args = parser.parse_args()

    batch=[]
    for i in range(args.count):
        evt = make_event(args.topic, args.source, i)
        batch.append(evt)
        if len(batch) >= 50:
            publish_batch(args.url, batch)
            batch=[]
            time.sleep(0.01)
    if batch:
        publish_batch(args.url, batch)