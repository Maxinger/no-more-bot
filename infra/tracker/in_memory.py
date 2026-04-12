"""In-memory tracker implementation for tests and local usage."""

from __future__ import annotations

import datetime as dt
from datetime import timedelta, timezone

from domain.model.record import Activity, Record
from domain.ports.tracker import Tracker

from collections import defaultdict

class InMemoryTracker(Tracker):
    def __init__(self):
        self.events: list[Record] = []
        self.goals: dict[Activity, dict[dt.date, dt.time]] = defaultdict(dict)

    def record(
        self,
        user_id: int,
        activity: Activity,
        timestamp: dt.datetime | None = None,
    ) -> Record:
        record = Record(
            user_id=user_id,
            activity=activity,
            timestamp=timestamp or dt.datetime.now(timezone.utc),
        )
        self.events.append(record)
        return record

    def history(
        self,
        user_id: int,
        days: int = 14,
        activity: Activity | None = None,
    ) -> list[Record]:
        now = dt.datetime.now(timezone.utc)
        start_time = now - timedelta(days=days)
        matches = [
            (index, event)
            for index, event in enumerate(self.events)
            if event.user_id == user_id
            and event.timestamp >= start_time
            and (activity is None or event.activity == activity)
        ]
        matches.sort(key=lambda item: (item[1].timestamp, item[0]), reverse=True)
        return [event for _, event in matches]

    def set_goal(self, activity: Activity, week_start: dt.date, time: dt.time) -> None:
        self.goals[activity][week_start] = time

    def get_goal(self, activity: Activity, week_start: dt.date) -> dt.time:
        return self.goals[activity][week_start]

    def get_goals(
        self, activity: Activity, limit: int | None = 10
    ) -> list[tuple[dt.date, dt.time]]:
        by_week = self.goals.get(activity, {})
        if not by_week:
            return []
        weeks = sorted(by_week.keys())
        if limit is None:
            return [(w, by_week[w]) for w in weeks]
        return [(w, by_week[w]) for w in weeks[-limit:]]