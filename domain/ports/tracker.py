"""Tracker persistence port."""

from __future__ import annotations

from domain.model.record import Activity, Record


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
