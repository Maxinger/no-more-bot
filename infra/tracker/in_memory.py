"""In-memory tracker implementation for tests and local usage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from domain.model.record import Activity, Record
from domain.ports.tracker import Tracker


class InMemoryTracker(Tracker):
    def __init__(self):
        self.events: list[Record] = []

    def record(self, user_id: int, activity: Activity) -> Record:
        record = Record(user_id=user_id, activity=activity)
        self.events.append(record)
        return record

    def history(
        self,
        user_id: int,
        days: int = 14,
        activity: Activity | None = None,
    ) -> list[Record]:
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(days=days)
        return [
            event
            for event in reversed(self.events)
            if event.user_id == user_id
            and event.timestamp >= start_time
            and activity is None or event.activity == activity
        ]
