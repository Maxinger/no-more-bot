"""Repository contract for activity records."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from ddd.domain.record import Activity, Record, WeekStart


class RecordRepository(Protocol):
    def find(self, user_id: int, activity: Activity, date: date) -> Record | None:
        """Return the stored record for ``user_id``, ``activity``, and logical day ``date``, or ``None``.

        ``date`` is the logical calendar day (``record.time.date`` after cutoff rules).
        """
        raise NotImplementedError

    def find_for_week(
        self, user_id: int, activity: Activity, week: WeekStart
    ) -> tuple[Record, ...]:
        """Return records whose logical days fall within ``week`` Monday through Sunday."""
        raise NotImplementedError

    def save(self, record: Record) -> None:
        """Persist ``record``, replacing any existing row for the same user, activity, and logical day."""
        raise NotImplementedError
