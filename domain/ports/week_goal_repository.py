"""Repository contract for per-week activity goals."""

from __future__ import annotations

from typing import Protocol

from domain.record import Activity, WeekStart
from domain.week_goal import WeekGoal


class WeekGoalRepository(Protocol):
    def find(self, user_id: int, activity: Activity, week: WeekStart) -> WeekGoal | None:
        raise NotImplementedError

    def find_all_for_user(self, user_id: int) -> tuple[WeekGoal, ...]:
        """Return all goals for ``user_id``, sorted by week start then activity."""
        raise NotImplementedError

    def save(self, goal: WeekGoal) -> None:
        """Persist ``goal``, upserting on ``(user_id, activity, week.value)`` (Monday date)."""
        raise NotImplementedError
