from pydantic import BaseModel, Field
from typing import Any, Dict
from datetime import datetime

class EventModel(BaseModel):
    topic: str = Field(..., min_length=1)
    event_id: str = Field(..., min_length=1)
    timestamp: str  # Expect ISO8601 string
    source: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        schema_extra = {
            "example": {
                "topic": "app.logs",
                "event_id": "evt-12345",
                "timestamp": "2025-10-23T08:00:00Z",
                "source": "service-A",
                "payload": {"level": "INFO", "msg": "something happened"}
            }
        }