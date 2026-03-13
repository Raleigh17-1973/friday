import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from packages.common.models import utc_now_iso


@dataclass
class Event:
    event_type: str  # "document.generated", "email.sent", etc.
    payload: dict[str, Any]
    timestamp: str = field(default_factory=utc_now_iso)
    source: str = "friday"


class EventBus:
    """Simple in-process pub/sub. Upgrade to Redis Streams for production."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._history: list[Event] = []
        self._log = logging.getLogger("events")

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):
        self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        self._history.append(event)
        self._log.info("Event: %s", event.event_type)
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                self._log.error("Handler failed for %s: %s", event.event_type, e)

    def recent_events(self, limit: int = 50) -> list[Event]:
        return list(reversed(self._history[-limit:]))
