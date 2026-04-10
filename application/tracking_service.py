"""Application service for activity tracking use cases."""

from __future__ import annotations

import datetime

from domain.model.record import Activity, Record
from domain.ports.tracker import Tracker


def _today_utc_date() -> datetime.date:
    return datetime.datetime.now(datetime.timezone.utc).date()


def monday_of_week_containing(day: datetime.date) -> datetime.date:
    """Monday (week start) of the ISO week that contains ``day`` (``weekday()`` Monday = 0)."""
    return day - datetime.timedelta(days=day.weekday())


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

    def set_goal(
        self,
        activity: Activity,
        time: datetime.time,
        week_start: datetime.date | None = None,
    ) -> None:
        ws = week_start if week_start is not None else monday_of_week_containing(_today_utc_date())
        return self.tracker.set_goal(activity, ws, time)

    def get_goal(self, activity: Activity, week_start: datetime.date | None = None) -> datetime.time:
        ws = week_start if week_start is not None else monday_of_week_containing(_today_utc_date())
        return self.tracker.get_goal(activity, ws)

    def get_goals(
        self, activity: Activity, limit: int = 10
    ) -> list[tuple[datetime.date, datetime.time]]:
        return self.tracker.get_goals(activity, limit)
