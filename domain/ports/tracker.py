"""Tracker persistence port."""

from __future__ import annotations

from domain.model.record import Activity, Record
import datetime


class Tracker:
    def record(self, user_id: int, activity: Activity) -> Record:
        """Persist one activity record and return the saved record."""
        raise NotImplementedError

    def history(
        self,
        user_id: int,
        days: int = 14,
        activity: Activity | None = None,
    ) -> list[Record]:
        """Return activity records for the last `days`, most recent first."""
        raise NotImplementedError

    def set_goal(self, activity: Activity, week_start: datetime.date, time: datetime.time) -> None:
        """Set the goal for the given activity and week start."""
        raise NotImplementedError

    def get_goal(self, activity: Activity, week_start: datetime.date) -> datetime.time:
        """Get the goal for the given activity and week start."""
        raise NotImplementedError

    def get_goals(
        self, activity: Activity, limit: int = 10
    ) -> list[tuple[datetime.date, datetime.time]]:
        """Return up to ``limit`` (week start, goal time) pairs for ``activity``, oldest week first."""
        raise NotImplementedError