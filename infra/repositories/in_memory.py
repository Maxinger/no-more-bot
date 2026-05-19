"""In-memory repository implementations for local wiring."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from domain.ports import RecordRepository, WeekGoalRepository
from domain.record import Activity, Record, WeekStart
from domain.week_goal import WeekGoal


RecordKey = tuple[int, Activity, date]
WeekGoalKey = tuple[int, Activity, date]


@dataclass
class InMemoryRecordRepository(RecordRepository):
    """Stores one record per user, activity, and logical day."""

    _by_key: dict[RecordKey, Record] = field(default_factory=dict)

    def find(self, user_id: int, activity: Activity, date: date) -> Record | None:
        return self._by_key.get((user_id, activity, date))

    def find_for_week(
        self, user_id: int, activity: Activity, week: WeekStart
    ) -> tuple[Record, ...]:
        start = week.value
        end = start + timedelta(days=6)
        return tuple(
            record
            for (record_user_id, record_activity, logical_day), record in sorted(
                self._by_key.items(), key=lambda item: item[0][2]
            )
            if record_user_id == user_id
            and record_activity == activity
            and start <= logical_day <= end
        )

    def find_all_for_user(self, user_id: int) -> tuple[Record, ...]:
        return tuple(
            record
            for (record_user_id, record_activity, logical_day), record in sorted(
                self._by_key.items(),
                key=lambda item: (item[0][2], item[0][1].value),
            )
            if record_user_id == user_id
        )

    def save(self, record: Record) -> None:
        self._by_key[(record.user_id, record.activity, record.time.date)] = record


@dataclass
class InMemoryWeekGoalRepository(WeekGoalRepository):
    """Stores one goal per user, activity, and week start."""

    _by_key: dict[WeekGoalKey, WeekGoal] = field(default_factory=dict)

    def find(self, user_id: int, activity: Activity, week: WeekStart) -> WeekGoal | None:
        return self._by_key.get((user_id, activity, week.value))

    def find_all_for_user(self, user_id: int) -> tuple[WeekGoal, ...]:
        return tuple(
            goal
            for (goal_user_id, goal_activity, week_start), goal in sorted(
                self._by_key.items(),
                key=lambda item: (item[0][2], item[0][1].value),
            )
            if goal_user_id == user_id
        )

    def save(self, goal: WeekGoal) -> None:
        self._by_key[(goal.user_id, goal.activity, goal.week.value)] = goal


@dataclass(frozen=True)
class InMemoryRepositories:
    """Small composition helper for sharing in-memory repositories."""

    records: InMemoryRecordRepository = field(default_factory=InMemoryRecordRepository)
    goals: InMemoryWeekGoalRepository = field(default_factory=InMemoryWeekGoalRepository)
