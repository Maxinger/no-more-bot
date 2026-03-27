"""Application service for activity tracking use cases."""

from __future__ import annotations

from domain.model.record import Activity, Record
from domain.ports.tracker import Tracker


class TrackingService:
    def __init__(self, tracker: Tracker):
        self.tracker = tracker

    def record(self, user_id: int, activity: Activity) -> Record:
        return self.tracker.record(user_id, activity)

    def history(
        self,
        user_id: int,
        days: int = 14,
        activity: Activity | None = None,
    ) -> list[Record]:
        return self.tracker.history(user_id, days, activity)
